"""Write a finished run's results back into the study inside the package.

Replacement semantics: ``ResultsType`` carries no id and no name in the
schema, so a result written earlier cannot be recognized and updated in
place. :func:`record_result` therefore replaces the ``ResultSet`` of the
activity it records into entirely, which makes a second run byte-stable
against the first. Hand-built results that must survive belong in another
activity, or must be re-supplied after each recording.

What is written: one ``Results`` element holding the metrics (a
``DomainViolationCount`` per monitored domain plus a ``SampleCount``), with
the optional per-variable ``Normal`` summaries appended to it. When the
run's samples are given, a second, otherwise-empty ``Results`` element
references them: the sample table is stored as a CSV entry under
``resources/uq/`` in the :class:`~omuq.simulation.CsvSink` format (so
:func:`omuq.fitting.samples_from_csv` reads it back), and the element
carries ``source``/``type``/``checksum``/``checksumType`` per guideline
section 6. The checksum is computed over the exact bytes written; a
corrupted entry is reported by ``validate(level=2)`` as ``L2.checksum``.

What is not written: coverage classifications.
:func:`coverage_from_result` builds a ``DomainCoverage`` from a run, but
does not classify a run that left its domain; the caller must say whether
the excursion is ``HighRisk``, ``AcceptableRisk`` or immaterial.
``Percentiles`` and ``SobolIndices`` are request-only in the schema (they
live in ``DesiredResults``) and have no result-side element to write into.

Imports: this module may import :mod:`omuq.model`, :mod:`omuq.simulation`
and :mod:`omuq.errors` at module scope. :mod:`omuq.package` imports this
module function-locally from the two :class:`~omuq.package.UqManager`
methods that delegate here, which keeps the package layer free of a
simulation dependency. Everything this module does to a package goes
through the public :class:`~omuq.package.SspPackage` API
(``has_entry``/``add_entry``/``replace_entry``), so the write-back never
needs the manager itself.
"""

from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import statistics
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import model
from ._xml import serialize_study, stamp_generation_info
from .constants import UQ_RESOURCE_DIR, UQ_SUFFIX
from .errors import LinkError, ModelError
from .simulation import Sample, SimulationResult

if TYPE_CHECKING:
    # Annotation-only: importing the package layer here at module scope
    # would close the cycle package -> writeback -> package.
    from .package import AttachedStudy, SspPackage

#: ``ErrorMetric/@type`` of the per-domain excursion count.
VIOLATION_METRIC = "DomainViolationCount"

#: ``ErrorMetric/@type`` of the number of samples the run delivered.
SAMPLE_COUNT_METRIC = "SampleCount"

#: ``Results/@type`` of an externalized sample table.
CSV_MIME = "text/csv"

#: ``Results/@checksumType`` spelling recommended by guideline section 6.3;
#: :mod:`omuq.validation` normalizes it before looking the algorithm up.
CHECKSUM_TYPE = "sha-256"

#: Suffix of the default sample-table entry name.
CSV_SUFFIX = ".results.csv"


@dataclass(frozen=True)
class RecordedResult:
    """What :meth:`omuq.package.UqManager.record_result` wrote.

    ``entry`` is the study document's package entry (rewritten unless
    ``update=False``), ``csv_entry`` the sample table's entry or ``None``
    when no samples were stored, and ``metrics``/``summaries`` count the
    ``ErrorMetric`` and ``Normal`` elements of the new ``ResultSet``.
    """

    entry: str
    csv_entry: str | None
    metrics: int
    summaries: int


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _require_file_backed(attached: AttachedStudy) -> str:
    """The study's package entry, or a :class:`~omuq.errors.LinkError`."""
    if attached.entry is None:
        raise LinkError(
            "write-back requires a file-backed study: this one is stored as "
            "inline ssc:MetaData/Content inside its host document, and "
            "omuq-python only rewrites omuq documents that have their own "
            "package entry (guideline section 4.1 recommends "
            "resources/uq/<name>.uq.xml). Re-attach the study with "
            "pkg.uq.attach(document, anchor) to give it one, then record "
            "into that"
        )
    return attached.entry


def _resolve_activity(
    document: model.Study, activity: int | str | model.Activity
) -> tuple[model.Activity, int]:
    """The activity to record into, plus its position in the document.

    Resolution matches :meth:`omuq.simulation.Simulation.for_study`: a
    position, an id or name, or the activity object itself. The object
    form is matched by identity rather than equality, because the results
    are written into that object: an equal activity from another (or a
    copied) document would receive them instead of this document.
    """
    activities = model.activities_of(document)
    resolved = (
        model.activity_of(document, activity)
        if isinstance(activity, (int, str))
        else activity
    )
    for index, candidate in enumerate(activities):
        if candidate is resolved:
            return resolved, index
    raise ModelError(
        f"the given activity is not part of study {document.name!r}, so "
        "recording into it would write results nowhere; pass the activity's "
        "position, its id or name, or an object taken from this document "
        "(e.g. omuq.model.activity_of(study, 0))"
    )


def _activity_key(activity: model.Activity, index: int) -> str:
    """The activity's id, or a stable fallback derived from its position."""
    return activity.id or f"activity{index}"


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def update_study(pkg: SspPackage, attached: AttachedStudy) -> None:
    """Re-serialize ``attached.document`` into its package entry.

    Implements :meth:`omuq.package.UqManager.update`; see there for the
    contract.
    """
    entry = _require_file_backed(attached)
    stamp_generation_info(attached.document, refresh=True)
    pkg.replace_entry(entry, serialize_study(attached.document))


# ---------------------------------------------------------------------------
# record_result
# ---------------------------------------------------------------------------


def _metrics(result: SimulationResult) -> list[model.ErrorMetric]:
    """One ``DomainViolationCount`` per monitored domain, then ``SampleCount``.

    Sorted by domain id rather than left in monitoring order, so the
    output does not depend on the order the study lists its domains.
    """
    metrics = [
        model.error_metric(
            VIOLATION_METRIC,
            float(count),
            name=domain_id,
            threshold=0.0,
            passed=count == 0,
        )
        for domain_id, count in sorted(result.samples_outside.items())
    ]
    metrics.append(model.error_metric(SAMPLE_COUNT_METRIC, float(result.steps + 1)))
    return metrics


def _summaries(
    activity: model.Activity, samples: Sequence[Sample], choice: bool | str
) -> list[model.ResultsNormal]:
    """Per-observed-variable ``Normal(mu, sigma)`` summaries of ``samples``.

    ``sigma`` is the population standard deviation
    (:func:`statistics.pstdev`), not the sample estimator: the samples are
    the whole run, not a draw from it, and pstdev is defined for a
    single-sample run where :func:`statistics.stdev` would raise.

    ``choice`` is ``record_result``'s ``summaries=``: ``"auto"`` writes
    them only when the activity's ``DesiredResults`` asked for a mean or a
    standard deviation and samples are available, ``True`` forces them
    (and raises when no samples were passed), ``False`` suppresses them.
    """
    if choice is False:
        return []
    if choice is True:
        if not samples:
            raise ModelError(
                "summaries=True needs the run's samples to summarize; pass "
                "samples=sink.samples (e.g. from an omuq.MemorySink), or "
                "leave summaries='auto'"
            )
    elif choice == "auto":
        desired = getattr(activity, "desired_results", None)
        if not samples or desired is None:
            return []
        if not (desired.mean or desired.standard_deviation):
            return []
    else:
        raise ModelError(
            f"summaries={choice!r} is not a valid choice; pass 'auto' (write "
            "summaries when the activity's DesiredResults asks for a mean or "
            "a standard deviation), True (always), or False (never)"
        )

    normals: list[model.ResultsNormal] = []
    for name in model.observed_names(activity):
        try:
            values = [float(s.values[name]) for s in samples]
        except KeyError:
            raise ModelError(
                f"the samples carry no values for observed variable {name!r}, "
                "so it cannot be summarized; the samples must come from a run "
                "of this activity"
            ) from None
        normals.append(
            model.ResultsNormal(
                mu=statistics.fmean(values), sigma=statistics.pstdev(values)
            )
        )
    return normals


def _csv_entry_name(
    entry: str,
    store_samples: bool | str,
    key: str,
    *,
    attached_entries: Collection[str] = (),
) -> str:
    """The sample table's entry name: derived, or explicit.

    The derived name shares the study document's file stem (via
    package.py's slug helper), so a study and its result tables sit
    together under ``resources/uq/``.

    An explicit ``store_samples="name.csv"`` must stay inside that
    directory (guideline section 6.1: omuq data stays in one place, and
    the entry is referenced from the document by a relative source); must
    end in ``.csv``; and must not end in the study-document suffix
    (``constants.UQ_SUFFIX``) or name any entry in ``attached_entries``
    (the package entry of every attached study, supplied by
    :meth:`omuq.package.UqManager.record_result`). These checks prevent
    :func:`record_result` from overwriting a study document with CSV bytes
    at the ``replace_entry`` call further down.
    """
    # Deferred import: package.py imports this module function-locally,
    # so importing it here at call time avoids an import cycle.
    from .package import _entry_slug

    if isinstance(store_samples, str):
        if not store_samples:
            raise ModelError(
                "store_samples='' is not a file name; pass a file name to "
                f"place inside {UQ_RESOURCE_DIR}/, True for the default name, "
                "or False to record the metrics without a sample table"
            )
        if store_samples.endswith(UQ_SUFFIX):
            raise ModelError(
                f"store_samples={store_samples!r} ends with {UQ_SUFFIX!r}, "
                "the suffix reserved for omuq study documents; recording "
                "samples there would overwrite a study document (possibly "
                "this one) instead of writing a CSV. Pass a name ending in "
                "'.csv'"
            )
        if not store_samples.endswith(".csv"):
            raise ModelError(
                f"store_samples={store_samples!r} does not end in '.csv'; "
                "pass a file name ending in '.csv' to place inside "
                f"{UQ_RESOURCE_DIR}/, True for the default name, or False "
                "to record the metrics without a sample table"
            )
        target = posixpath.normpath(posixpath.join(UQ_RESOURCE_DIR, store_samples))
        if not target.startswith(UQ_RESOURCE_DIR + "/"):
            raise ModelError(
                f"store_samples={store_samples!r} resolves to {target!r}, "
                f"outside {UQ_RESOURCE_DIR}/; omuq data stays in that "
                "directory (guideline section 4.1), so pass a plain file name"
            )
        if target in attached_entries:
            raise ModelError(
                f"store_samples={store_samples!r} resolves to {target!r}, "
                "which is the package entry of a study attached to this "
                "package; recording samples there would overwrite that "
                "document. Pass a different file name"
            )
        return target
    stem = _entry_slug(posixpath.basename(entry))
    return f"{UQ_RESOURCE_DIR}/{stem}-{key}{CSV_SUFFIX}"


def _csv_bytes(result: SimulationResult, samples: Sequence[Sample]) -> bytes:
    """The samples in :class:`~omuq.simulation.CsvSink`'s exact format.

    Columns are the run's observed variables in declaration order, looked
    up by name rather than by the order each sample stores them in.
    ``csv.writer`` on an untranslated buffer produces the same output as
    the sink, including its ``\\r\\n`` line terminator, so
    :func:`omuq.fitting.samples_from_csv` can read the entry back.
    """
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["time", *result.names])
    for sample in samples:
        missing = [n for n in result.names if n not in sample.values]
        if missing:
            raise ModelError(
                f"the sample at t={sample.time!r} has no value for "
                f"{', '.join(repr(n) for n in missing)}; the samples must "
                "come from the run being recorded (its observed variables "
                f"are {', '.join(repr(n) for n in result.names)})"
            )
        writer.writerow([sample.time, *(sample.values[n] for n in result.names)])
    return buf.getvalue().encode("utf-8")


def _external_results(*, source: str, checksum: str) -> model.ResultsType:
    """An empty ``Results`` element pointing at an in-package data file.

    The external-source attributes are set on the built element rather
    than passed to :func:`omuq.model.results`, which only builds the
    contents of a ``Results``.
    """
    results = model.results()
    results.source = source
    results.type_value = CSV_MIME
    results.checksum = checksum
    results.checksum_type = CHECKSUM_TYPE
    return results


def record_result(
    pkg: SspPackage,
    attached: AttachedStudy,
    result: SimulationResult,
    *,
    activity: int | str | model.Activity = 0,
    samples: Sequence[Sample] | None = None,
    store_samples: bool | str = True,
    summaries: bool | str = "auto",
    update: bool = True,
    attached_entries: Collection[str] = (),
) -> RecordedResult:
    """Record a finished run into one activity of an attached study.

    Implements :meth:`omuq.package.UqManager.record_result`; see there for
    the contract and this module's docstring for the design.
    ``attached_entries`` is the package entry of every study currently
    attached (from :meth:`omuq.package.UqManager._attached_entries`),
    passed in by that method so an explicit ``store_samples=`` can be
    checked against it without importing the manager here (see the module
    docstring). Other callers may leave it empty and lose only that check.
    """
    entry = _require_file_backed(attached)
    act, index = _resolve_activity(attached.document, activity)
    rows = list(samples or ())

    # Everything that can be rejected is computed before anything is
    # written, so a bad argument cannot leave a half-recorded package
    # behind (a stored CSV without an updated document, or the reverse).
    metrics = _metrics(result)
    normals = _summaries(act, rows, summaries)
    csv_entry: str | None = None
    payload = b""
    if isinstance(store_samples, str) or store_samples:
        name = _csv_entry_name(
            entry,
            store_samples,
            _activity_key(act, index),
            attached_entries=attached_entries,
        )
        if rows:
            csv_entry, payload = name, _csv_bytes(result, rows)
        elif isinstance(store_samples, str):
            raise ModelError(
                f"store_samples={store_samples!r} asks for a sample table, but "
                "no samples were given to write into it; pass "
                "samples=sink.samples (e.g. from an omuq.MemorySink), or "
                "store_samples=False"
            )

    elements = [model.results(*metrics, *normals)]
    if csv_entry is not None:
        if pkg.has_entry(csv_entry):
            pkg.replace_entry(csv_entry, payload)
        else:
            pkg.add_entry(csv_entry, payload)
        elements.append(
            _external_results(
                source=posixpath.relpath(csv_entry, posixpath.dirname(entry) or "."),
                checksum=hashlib.sha256(payload).hexdigest(),
            )
        )
    act.result_set = model.result_set(*elements)

    if update:
        update_study(pkg, attached)
    return RecordedResult(
        entry=entry,
        csv_entry=csv_entry,
        metrics=len(metrics),
        summaries=len(normals),
    )


# ---------------------------------------------------------------------------
# coverage_from_result
# ---------------------------------------------------------------------------


def coverage_from_result(
    result: SimulationResult,
    *,
    requested: str,
    realized: str,
    domain_id: str | None = None,
    when_clean: model.CoverageClassificationType | str = "Covered",
    when_violated: model.CoverageClassificationType | str | None = None,
    id: str | None = None,
    description: str | None = None,
) -> model.DomainCoverageType:
    """Build a ``DomainCoverage`` from a run's domain-excursion counts.

    ``requested`` and ``realized`` are the ids of the two domains being
    compared, typically the domain that was monitored and one representing
    the run itself (e.g. a boundary fitted to its samples with
    :func:`omuq.fitting.fit_operational_domain`). ``domain_id`` names the
    :attr:`~omuq.simulation.SimulationResult.samples_outside` entry to
    read when that is neither of them; it defaults to ``requested``.

    A run that never left the domain is recorded as ``when_clean``
    (``"Covered"``). A run that did leave it is not classified
    automatically: without ``when_violated`` this raises
    :class:`~omuq.errors.ModelError`, since classifying an excursion is
    the caller's decision. The counts are written into the coverage's
    description.

    The default ``id`` (``coverage-<requested>-<realized>``) is stable
    across runs, so re-recording the same comparison through
    :func:`omuq.model.upsert_coverage` replaces it instead of adding
    duplicates.
    """
    key = domain_id or requested
    if key not in result.samples_outside:
        monitored = ", ".join(repr(d) for d in result.monitored_domains) or "none"
        raise ModelError(
            f"this run did not monitor domain {key!r}, so it says nothing "
            f"about that domain's coverage (monitored: {monitored}); monitor "
            "it during the run, or pass domain_id= to read the counts of a "
            "domain that was"
        )
    outside = result.samples_outside[key]
    total = result.steps + 1
    if outside and when_violated is None:
        raise ModelError(
            f"{outside} of {total} samples fell outside {key!r}: this run left "
            "the domain, and how much that matters is a human judgment the "
            "SDK will not make for you. Pass when_violated= with the "
            "classification this excursion deserves ('HighRisk', "
            "'AcceptableRisk', 'NotNeeded', or 'Covered' if it is immaterial)"
        )
    classification = when_clean if outside == 0 else when_violated
    if description is None:
        description = f"run: {outside} of {total} samples outside {key}"
    return model.domain_coverage(
        requested,
        realized,
        regions=[(classification,)],
        id=id if id is not None else f"coverage-{requested}-{realized}",
        description=description,
    )
