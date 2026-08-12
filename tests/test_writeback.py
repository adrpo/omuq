import hashlib
import io
import re
import statistics
import zipfile

import pytest
from conftest import EXTRA, FMU, FakeDriver, reopen
from lxml import etree
from xsdata.models.datatype import XmlDateTime

from omuq import (
    LinkError,
    MemorySink,
    ModelError,
    RecordedResult,
    Simulation,
    SsdRootAnchor,
    coverage_from_result,
    model,
    parse_study,
    samples_from_csv,
    serialize_study,
)
from omuq.constants import MIME_OMUQ, NS_SSC, UQ_SUFFIX

#: Observed variables that exist in the conftest SSD (a declared output and a
#: declared parameter connector on ``battery``), so a recorded document still
#: passes validate(level=3) without L3 warnings.
OBSERVED = ("battery.V", "battery.R0")


def run_study(
    name="BatteryUQ",
    *,
    desired=None,
    activity_id="fuq1",
    hi=(0.3,),
    observed=OBSERVED,
):
    """A one-activity study with a monitorable domain of validation.

    The FakeDriver reads the i-th observed variable as ``t + 10 * i``, so
    over the 0.25/1.0 grid ``battery.V`` walks 0, 0.25, ... 1.0 and leaves
    the default ``dov`` box (``hi=(0.3,)``) for its last three samples.
    """
    return model.study(
        name,
        activities=[
            model.forward_uq(
                observed=list(observed),
                step=0.25,
                stop=1.0,
                samples=8,
                desired=desired,
                domain_ref="dov",
                id=activity_id,
            )
        ],
        domains=[
            model.activity_domain(
                "dov", [observed[0]], model.hyper_rectangle((0.0,), hi)
            )
        ],
    )


def drive(study, activity=0):
    """Run a study on the deterministic FakeDriver: (result, samples)."""
    sink = MemorySink()
    sim = Simulation.for_study(study, FakeDriver(), activity=activity)
    sim.subscribe(sink)
    return sim.run(), sink.samples


def attach_inline(pkg, study):
    """Attach a study as inline ``ssc:MetaData/Content`` (no package entry)."""
    host = pkg.ssd()
    md = host.inject_metadata(
        host.root, "ssd_root", source="placeholder", mime=MIME_OMUQ, kind="quality"
    )
    del md.attrib["source"]
    content = etree.SubElement(md, f"{{{NS_SSC}}}Content")
    content.append(etree.fromstring(serialize_study(study)))
    pkg._mark_dirty(host.entry)
    return pkg.uq.study()


def metrics_of(activity):
    """The ErrorMetrics of an activity's first Results element."""
    items = model.result_items(model.results_of(activity)[0])
    return [i for i in items if isinstance(i, model.ErrorMetric)]


def normals_of(activity):
    """The result Normals of an activity's first Results element."""
    items = model.result_items(model.results_of(activity)[0])
    return [i for i in items if isinstance(i, model.ResultsNormal)]


def first_activity(pkg):
    return model.activity_of(pkg.uq.study().document)


def codes(report):
    return {i.code for i in report.errors}


def without_stamp(data: bytes):
    """A parsed document with its generation timestamp blanked out."""
    doc = parse_study(data)
    doc.generation_date_and_time = None
    return doc


@pytest.fixture()
def run(pkg):
    """Attach the fixture study and drive it: (attached, result, samples)."""
    study = run_study()
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    return attached, result, samples


# -- metrics ---------------------------------------------------------------


def test_record_result_writes_metrics_and_validates(pkg, run):
    attached, result, samples = run
    assert result.samples_outside == {"dov": 3} and result.steps == 4

    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert isinstance(recorded, RecordedResult)
    assert recorded.entry == "resources/uq/BatteryUQ.uq.xml"
    assert (recorded.metrics, recorded.summaries) == (2, 0)

    pkg2, _ = reopen(pkg)
    metrics = metrics_of(first_activity(pkg2))
    assert [(m.type_value, m.name, m.value, m.pass_value) for m in metrics] == [
        ("DomainViolationCount", "dov", 3.0, False),
        ("SampleCount", None, 5.0, None),
    ]
    assert metrics[0].threshold == 0.0
    report = pkg2.uq.validate(level=3)
    assert report.ok, str(report)


def test_a_clean_run_passes_its_domain_metric(pkg):
    study = run_study(hi=(2.0,))
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    pkg.uq.record_result(attached, result, samples=samples)
    metric = metrics_of(first_activity(pkg))[0]
    assert (metric.value, metric.pass_value) == (0.0, True)


def test_domain_metrics_are_written_in_a_deterministic_order(pkg):
    study = model.study(
        "Ordered",
        activities=[
            model.forward_uq(observed=list(OBSERVED), step=0.5, stop=1.0, id="fuq1")
        ],
        domains=[
            model.activity_domain(
                "zdov", [OBSERVED[0]], model.hyper_rectangle((0.0,), (0.3,))
            ),
            model.activity_domain(
                "adov", [OBSERVED[0]], model.hyper_rectangle((0.0,), (0.3,))
            ),
        ],
    )
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    assert list(result.samples_outside) == ["zdov", "adov"]  # document order
    pkg.uq.record_result(attached, result, samples=samples)
    assert [m.name for m in metrics_of(first_activity(pkg))] == ["adov", "zdov", None]


# -- the samples CSV -------------------------------------------------------


def test_samples_csv_round_trips_and_is_checksummed(pkg, run, tmp_path):
    attached, result, samples = run
    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert recorded.csv_entry == "resources/uq/BatteryUQ-fuq1.results.csv"
    assert recorded.csv_entry in pkg.entry_names()

    payload = pkg.read(recorded.csv_entry)
    assert payload.startswith(b"time,battery.V,battery.R0\r\n")
    path = tmp_path / "back.csv"
    path.write_bytes(payload)
    back = samples_from_csv(path)
    assert [s.time for s in back] == [s.time for s in samples]
    assert [s.values for s in back] == [s.values for s in samples]

    external = [r for r in model.results_of(first_activity(pkg)) if r.source]
    assert len(external) == 1
    assert external[0].source == "BatteryUQ-fuq1.results.csv"
    assert external[0].type_value == "text/csv"
    assert external[0].checksum_type == "sha-256"
    assert external[0].checksum == hashlib.sha256(payload).hexdigest()
    assert model.result_items(external[0]) == []
    assert pkg.uq.validate(level=3).ok


def test_corrupting_the_csv_is_caught_by_the_checksum(pkg, run):
    attached, result, samples = run
    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert pkg.uq.validate(level=2).ok

    pkg.replace_entry(recorded.csv_entry, b"time,battery.V,battery.R0\r\n0,9,9\r\n")
    assert "L2.checksum" in codes(pkg.uq.validate(level=2))


def test_default_csv_name_uses_the_activity_position_without_an_id(pkg):
    study = run_study(activity_id=None)
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert recorded.csv_entry == "resources/uq/BatteryUQ-activity0.results.csv"


def test_store_samples_false_records_metrics_only(pkg, run):
    attached, result, samples = run
    recorded = pkg.uq.record_result(
        attached, result, samples=samples, store_samples=False
    )
    assert recorded.csv_entry is None
    assert [n for n in pkg.entry_names() if n.endswith(".csv")] == []
    assert [r.source for r in model.results_of(first_activity(pkg))] == [None]


def test_without_samples_only_metrics_are_written(pkg, run):
    attached, result, _ = run
    recorded = pkg.uq.record_result(attached, result)
    assert (recorded.csv_entry, recorded.metrics) == (None, 2)
    assert len(model.results_of(first_activity(pkg))) == 1


def test_store_samples_accepts_a_file_name_under_resources_uq(pkg, run):
    attached, result, samples = run
    recorded = pkg.uq.record_result(
        attached, result, samples=samples, store_samples="run-42.csv"
    )
    assert recorded.csv_entry == "resources/uq/run-42.csv"
    assert pkg.uq.validate(level=2).ok


@pytest.mark.parametrize("name", ["../escape.csv", "/abs.csv", "..", ""])
def test_store_samples_rejects_names_outside_resources_uq(pkg, run, name):
    attached, result, samples = run
    with pytest.raises(ModelError, match="resources/uq"):
        pkg.uq.record_result(attached, result, samples=samples, store_samples=name)
    assert [n for n in pkg.entry_names() if n.endswith(".csv")] == []


# -- store_samples cannot target a study document ---------------------------


@pytest.mark.parametrize("name", [f"BatteryUQ{UQ_SUFFIX}", f"nonexistent{UQ_SUFFIX}"])
def test_store_samples_refuses_a_uq_xml_target(pkg, run, name):
    """A name ending in the study suffix is refused outright.

    Demonstrated bug this guards against: store_samples naming the attached
    study's own entry ("BatteryUQ.uq.xml") used to silently replace that
    document with CSV bytes via replace_entry -- after which
    pkg.uq.validate() crashed with a raw xsdata ParserError instead of
    reporting anything. ``update=False`` is passed because the corruption
    happened in the CSV-writing step, unconditionally on ``update``.
    """
    attached, result, samples = run
    before = pkg.read(attached.entry)
    with pytest.raises(ModelError, match=re.escape(UQ_SUFFIX)):
        pkg.uq.record_result(
            attached, result, samples=samples, store_samples=name, update=False
        )
    assert pkg.read(attached.entry) == before
    assert pkg.uq.validate(level=3).ok


def test_store_samples_refuses_a_name_equal_to_another_studys_entry(pkg, run):
    """A ``.csv``-suffixed name is still refused if it names a live entry.

    Uses an entry that does not end in UQ_SUFFIX (attached by hand,
    bypassing ``attach()``, which always appends it) so this exercises the
    entry-collision check on its own, not the UQ_SUFFIX check above.
    """
    attached, result, samples = run
    other_entry = "resources/uq/other.csv"
    pkg.add_entry(other_entry, serialize_study(run_study("Other")))
    host = pkg.ssd()
    host.inject_metadata(
        host.root, "ssd_root", source=other_entry, mime=MIME_OMUQ, kind="quality"
    )
    pkg._mark_dirty(host.entry)
    before = pkg.read(other_entry)

    with pytest.raises(ModelError, match="other.csv"):
        pkg.uq.record_result(
            attached, result, samples=samples, store_samples="other.csv"
        )
    assert pkg.read(other_entry) == before


def test_store_samples_requires_a_csv_suffix(pkg, run):
    attached, result, samples = run
    with pytest.raises(ModelError, match=r"\.csv"):
        pkg.uq.record_result(
            attached, result, samples=samples, store_samples="notes.txt"
        )
    assert not pkg.has_entry("resources/uq/notes.txt")


# -- a corrupted study document is reported, not raised ---------------------


def test_a_corrupted_study_entry_is_reported_not_raised(pkg, run):
    """UqManager._load wraps a parse failure in LinkError.

    Builds a package whose study entry is not a parseable omuq document
    (via replace_entry, which refuses host .ssd/.ssv entries but not this
    one) and checks that studies()/validate() report the problem through
    omuq's own exception hierarchy instead of leaking a raw xsdata/dataclass
    exception.
    """
    attached, _, _ = run
    pkg.replace_entry(attached.entry, b"not an omuq document, just garbage bytes")

    with pytest.raises(LinkError, match=re.escape(attached.entry)):
        pkg.uq.studies()

    report = pkg.uq.validate(level=3)
    assert not report.ok
    assert any(attached.entry in i.message for i in report.errors)


# -- idempotency -----------------------------------------------------------


def test_recording_twice_is_byte_stable_and_adds_no_entries(pkg, run):
    attached, result, samples = run
    first = pkg.uq.record_result(attached, result, samples=samples)
    before, names_before = pkg.read(first.entry), pkg.entry_names()

    second = pkg.uq.record_result(attached, result, samples=samples)
    assert second == first
    assert pkg.entry_names() == names_before
    assert len(names_before) == len(set(names_before))
    assert without_stamp(pkg.read(first.entry)) == without_stamp(before)

    activity = first_activity(pkg)
    assert len(model.results_of(activity)) == 2
    assert len(metrics_of(activity)) == 2

    # ... and the saved archive carries exactly one sample table
    _, out_bytes = reopen(pkg)
    names = zipfile.ZipFile(io.BytesIO(out_bytes)).namelist()
    assert names.count(first.csv_entry) == 1
    assert len(names) == len(set(names))


def test_a_second_record_replaces_the_whole_result_set(pkg):
    study = run_study(desired=model.desired_results(mean=True, std=True))
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    pkg.uq.record_result(attached, result, samples=samples)
    assert len(normals_of(first_activity(pkg))) == 2

    pkg.uq.record_result(attached, result, samples=samples, summaries=False)
    assert normals_of(first_activity(pkg)) == []
    assert len(metrics_of(first_activity(pkg))) == 2


# -- summaries -------------------------------------------------------------


def test_summaries_auto_follows_desired_results(pkg):
    study = run_study(desired=model.desired_results(mean=True, std=True))
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert recorded.summaries == 2

    pkg2, _ = reopen(pkg)
    normals = normals_of(first_activity(pkg2))
    want = [
        v
        for name in OBSERVED
        for v in (
            statistics.fmean([s.values[name] for s in samples]),
            statistics.pstdev([s.values[name] for s in samples]),
        )
    ]
    assert [v for n in normals for v in (n.mu, n.sigma)] == pytest.approx(want)
    # ObservedVariables document order: battery.V first, battery.R0 second
    assert (normals[0].mu, normals[1].mu) == (0.5, 10.5)
    assert pkg2.uq.validate(level=3).ok


def test_summaries_auto_stays_silent_without_desired_results(pkg, run):
    attached, result, samples = run
    recorded = pkg.uq.record_result(attached, result, samples=samples)
    assert recorded.summaries == 0
    assert normals_of(first_activity(pkg)) == []


def test_summaries_true_forces_them_without_desired_results(pkg, run):
    attached, result, samples = run
    recorded = pkg.uq.record_result(attached, result, samples=samples, summaries=True)
    assert recorded.summaries == 2


def test_summaries_true_without_samples_is_an_error(pkg, run):
    attached, result, _ = run
    with pytest.raises(ModelError, match="summaries=True"):
        pkg.uq.record_result(attached, result, summaries=True)
    assert model.results_of(first_activity(pkg)) == []


def test_unknown_summaries_choice_is_rejected(pkg, run):
    attached, result, samples = run
    with pytest.raises(ModelError, match="summaries="):
        pkg.uq.record_result(attached, result, samples=samples, summaries="always")


# -- update() --------------------------------------------------------------


def test_update_writes_the_mutated_document_and_refreshes_the_stamp(pkg):
    attached = pkg.uq.attach(run_study(), SsdRootAnchor())
    stale = XmlDateTime.from_string("2000-01-01T00:00:00Z")
    attached.document.generation_date_and_time = stale
    attached.document.info = "edited in memory"

    pkg.uq.update(attached)
    pkg2, _ = reopen(pkg)
    doc = pkg2.uq.study().document
    assert doc.info == "edited in memory"
    assert doc.generation_date_and_time != stale
    assert doc.generation_tool.startswith("omuq-python")


def test_record_result_with_update_false_leaves_the_entry_alone(pkg, run):
    attached, result, samples = run
    before = pkg.read(attached.entry)
    pkg.uq.record_result(attached, result, samples=samples, update=False)
    assert pkg.read(attached.entry) == before
    assert model.results_of(model.activity_of(attached.document))  # in memory only

    pkg.uq.update(attached)
    assert model.results_of(first_activity(pkg))


def test_update_refuses_an_inline_study(pkg):
    inline = attach_inline(pkg, run_study("Inline"))
    assert inline.entry is None
    with pytest.raises(LinkError, match="file-backed"):
        pkg.uq.update(inline)


def test_record_result_refuses_an_inline_study(pkg):
    inline = attach_inline(pkg, run_study("Inline"))
    result, samples = drive(inline.document)
    with pytest.raises(LinkError, match="file-backed"):
        pkg.uq.record_result(inline, result, samples=samples)
    assert model.results_of(model.activity_of(inline.document)) == []


# -- activity resolution ---------------------------------------------------


def test_activity_can_be_selected_by_id_object_or_index(pkg):
    study = model.study(
        "Two",
        activities=[
            model.forward_uq(observed=list(OBSERVED), step=0.5, stop=1.0, id="first"),
            model.forward_uq(observed=list(OBSERVED), step=0.5, stop=1.0, id="second"),
        ],
    )
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study, activity=1)
    recorded = pkg.uq.record_result(
        attached, result, samples=samples, activity="second"
    )
    assert recorded.csv_entry == "resources/uq/Two-second.results.csv"

    activities = model.activities_of(pkg.uq.study().document)
    assert model.results_of(activities[0]) == []
    assert len(model.results_of(activities[1])) == 2

    same = pkg.uq.record_result(
        attached, result, samples=samples, activity=model.activity_of(study, 1)
    )
    assert same == recorded


def test_an_activity_from_another_study_is_rejected(pkg, run):
    attached, result, samples = run
    stranger = model.activity_of(run_study("Other"))
    with pytest.raises(ModelError, match="not part of"):
        pkg.uq.record_result(attached, result, activity=stranger)


# -- coverage_from_result --------------------------------------------------


def test_coverage_from_a_clean_run_is_covered():
    result, _ = drive(run_study(hi=(2.0,)))
    cov = coverage_from_result(result, requested="dov", realized="fitted")
    assert cov.id == "coverage-dov-fitted"
    assert (cov.requested_domain_ref, cov.realized_domain_ref) == ("dov", "fitted")
    assert [r.classification for r in cov.region] == [
        model.CoverageClassificationType.COVERED
    ]
    assert cov.description == "run: 0 of 5 samples outside dov"


def test_coverage_refuses_to_classify_a_violated_run_on_its_own():
    result, _ = drive(run_study())
    with pytest.raises(ModelError, match="when_violated"):
        coverage_from_result(result, requested="dov", realized="fitted")


def test_coverage_records_the_human_decision_with_the_counts():
    result, _ = drive(run_study())
    cov = coverage_from_result(
        result,
        requested="dov",
        realized="fitted",
        when_violated="HighRisk",
        id="cov-1",
    )
    assert cov.id == "cov-1"
    assert [r.classification for r in cov.region] == [
        model.CoverageClassificationType.HIGH_RISK
    ]
    assert cov.description == "run: 3 of 5 samples outside dov"


def test_coverage_reads_an_explicit_domain_id_and_rejects_unmonitored_ones():
    result, _ = drive(run_study())
    cov = coverage_from_result(
        result,
        requested="requestedOd",
        realized="dov",
        domain_id="dov",
        when_violated="AcceptableRisk",
    )
    assert cov.description == "run: 3 of 5 samples outside dov"
    with pytest.raises(ModelError, match="did not monitor"):
        coverage_from_result(result, requested="ghost", realized="dov")


def test_coverage_upserts_by_id_and_validates(pkg):
    study = run_study()
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    model.add_domain(
        study,
        model.operational_domain(
            "fitted", [OBSERVED[0]], model.hyper_rectangle((0.0,), (1.0,))
        ),
    )
    for _ in range(2):
        model.upsert_coverage(
            study,
            coverage_from_result(
                result, requested="dov", realized="fitted", when_violated="HighRisk"
            ),
        )
    pkg.uq.record_result(attached, result, samples=samples)

    pkg2, _ = reopen(pkg)
    doc = pkg2.uq.study().document
    assert len(doc.domains.domain_coverage) == 1
    report = pkg2.uq.validate(level=3)
    assert report.ok, str(report)


def test_coverage_pointing_at_a_missing_domain_is_a_broken_ref(pkg):
    study = run_study()
    attached = pkg.uq.attach(study, SsdRootAnchor())
    result, samples = drive(study)
    model.upsert_coverage(
        study,
        coverage_from_result(
            result, requested="dov", realized="ghost", when_violated="HighRisk"
        ),
    )
    pkg.uq.record_result(attached, result, samples=samples)
    assert "L2.broken-ref" in codes(pkg.uq.validate(level=2))


# -- packaging fidelity ----------------------------------------------------


def test_untouched_entries_stay_byte_identical(pkg, ssp_bytes, run):
    attached, result, samples = run
    pkg.uq.record_result(attached, result, samples=samples)
    _, out_bytes = reopen(pkg)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        assert zf.read("extra/com.vendor.tool/notes.txt") == EXTRA
        assert zf.read("resources/battery.fmu") == FMU
        with zipfile.ZipFile(io.BytesIO(ssp_bytes)) as zin:
            assert zf.read("resources/params.ssv") == zin.read("resources/params.ssv")
