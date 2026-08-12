"""Builders, accessors and enums of the ``omuq.model`` curation layer.

Every must-have builder is exercised once on its own and once inside a
full study that is attached to a package, validated at level 1 (XSD) and
re-opened, checking end to end that the builders produce schema-valid
documents that survive a round trip.
"""

import pytest
from conftest import reopen

from omuq import SsdRootAnchor, model, parse_study, serialize_study
from omuq.errors import (
    DriverNotFoundError,
    FittingError,
    ModelError,
    OmuqError,
    SimulationError,
)

TETRA = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


# -- errors -----------------------------------------------------------------


def test_new_error_classes_exist():
    assert issubclass(ModelError, OmuqError)
    assert issubclass(FittingError, OmuqError)
    assert issubclass(DriverNotFoundError, SimulationError)


def test_attach_without_a_name_raises_model_error(pkg):
    with pytest.raises(ModelError, match="name"):
        pkg.uq.attach(model.Study(name=""), SsdRootAnchor())


# -- geometry builders ------------------------------------------------------


def test_axes_from_names_and_units():
    ax = model.axes("a", "b", units={"b": "m"})
    assert [a.name for a in ax.axis] == ["a", "b"]
    assert [a.unit for a in ax.axis] == [None, "m"]


def test_axes_rejects_units_for_unknown_axis():
    with pytest.raises(ModelError, match="c"):
        model.axes("a", "b", units={"c": "m"})


def test_axes_needs_at_least_one_name():
    with pytest.raises(ModelError):
        model.axes()


def test_convex_hull_coordinates_survive_points_of():
    hull = model.convex_hull([(0.1, 0.2), (1.5, -2.25), (3.0, 4.0)])
    assert isinstance(hull, model.ConvexHullType)
    assert model.points_of(hull) == [(0.1, 0.2), (1.5, -2.25), (3.0, 4.0)]


def test_convex_hull_rejects_ragged_points():
    with pytest.raises(ModelError, match="coordinate"):
        model.convex_hull([(0.0, 1.0), (2.0,)])


def test_convex_hull_rejects_empty_input():
    with pytest.raises(ModelError):
        model.convex_hull([])


def test_hyper_rectangle_from_two_corners():
    rect = model.hyper_rectangle([0, 1], [2, 3])
    assert model.points_of(rect) == [(0.0, 1.0), (2.0, 3.0)]


def test_hyper_rectangle_rejects_mismatched_corners():
    with pytest.raises(ModelError, match="coordinate"):
        model.hyper_rectangle([0, 1], [2])


def test_hyper_rectangle_rejects_inverted_corners():
    with pytest.raises(ModelError, match="lo"):
        model.hyper_rectangle([2, 0], [1, 1])


def test_boundary_wraps_a_shape():
    b = model.boundary(model.hyper_rectangle([0], [1]))
    assert isinstance(b, model.BoundaryType)
    assert isinstance(model.shape_of(b), model.HyperRectangleType)


def test_boundary_rejects_non_shapes():
    with pytest.raises(TypeError):
        model.boundary(model.AxesType())


# -- domain builders --------------------------------------------------------


def test_operational_domain_defaults_and_coercions():
    dom = model.operational_domain(
        "od1", ["x", "y"], model.hyper_rectangle([0, 0], [1, 1])
    )
    assert dom.kind is model.TypedOperationalDomainKind.MODELED_OPERATIONAL_DOMAIN
    assert dom.geometry_kind == "HyperRectangle"
    assert model.axis_names(dom) == ("x", "y")
    assert isinstance(dom.boundary, model.BoundaryType)
    assert model.points_of(dom) == [(0.0, 0.0), (1.0, 1.0)]


def test_operational_domain_accepts_string_kind_and_prebuilt_parts():
    dom = model.operational_domain(
        "od2",
        model.axes("x", "y", "z"),
        model.boundary(model.convex_hull(TETRA)),
        kind="RequestedOperationalDomain",
        name="Requested",
        description="what the customer asked for",
        parent_ref="od1",
    )
    assert dom.kind is model.TypedOperationalDomainKind.REQUESTED_OPERATIONAL_DOMAIN
    assert dom.geometry_kind == "ConvexHull"
    assert dom.parent_ref == "od1"
    assert dom.description == "what the customer asked for"


def test_operational_domain_unknown_kind_raises_model_error():
    with pytest.raises(ModelError, match="kind"):
        model.operational_domain(
            "od3", ["x"], model.hyper_rectangle([0], [1]), kind="Nope"
        )


def test_activity_domain_defaults_to_validation():
    dom = model.activity_domain(
        "ad1", ["x"], model.hyper_rectangle([0], [1]), domain_ref="od1"
    )
    assert dom.kind == "Validation"
    assert dom.domain_ref == "od1"
    assert model.axis_names(dom) == ("x",)


def test_domains_dispatches_by_type():
    od = model.operational_domain("od1", ["x"], model.hyper_rectangle([0], [1]))
    ad = model.activity_domain("ad1", ["x"], model.hyper_rectangle([0], [1]))
    cov = model.domain_coverage("od1", "ad1", regions=[("Covered",)])
    doms = model.domains(od, ad, cov)
    assert doms.typed_operational_domain == [od]
    assert doms.activity_domain == [ad]
    assert doms.domain_coverage == [cov]


def test_domains_rejects_junk():
    with pytest.raises(TypeError):
        model.domains("not a domain")


# -- activity builders ------------------------------------------------------


def test_forward_uq_stays_backward_compatible():
    act = model.forward_uq(
        uncertain=[model.uncertain_parameter("p", model.Normal(mu=0.0, sigma=1.0))],
        observed=["v"],
        samples=100,
        sampling="PseudoRandom",
        id="fuq1",
    )
    assert isinstance(act, model.ForwardUncertaintyQuantificationType)
    assert model.observed_names(act) == ("v",)
    method = model.sampling_of(act)
    assert isinstance(method, model.PseudoRandomType)
    assert method.number_of_samples == 100
    param = act.parameter_set.parameters.uncertain_parameter[0]
    assert model.distribution_of(param) == model.Normal(mu=0.0, sigma=1.0)


def test_forward_uq_rejects_name_and_description():
    with pytest.raises(TypeError, match="name"):
        model.forward_uq(observed=["v"], name="not in the schema")
    with pytest.raises(TypeError, match="description"):
        model.forward_uq(observed=["v"], description="not in the schema")


def test_forward_uq_rejects_truly_unknown_keywords():
    with pytest.raises(TypeError, match="nonsense"):
        model.forward_uq(nonsense=1)


def test_sampling_normalizes_str_and_enum():
    assert model.Sampling("LatinHyperCube") is model.Sampling.LATIN_HYPERCUBE
    act = model.forward_uq(samples=7, sampling=model.Sampling.PSEUDO_RANDOM)
    assert isinstance(model.sampling_of(act), model.PseudoRandomType)
    act = model.forward_uq(samples=7)  # default is LatinHyperCube
    assert isinstance(model.sampling_of(act), model.LatinHypercubeType)


def test_unknown_sampling_raises_model_error():
    with pytest.raises(ModelError, match="sampling"):
        model.forward_uq(samples=7, sampling="Sobol")


def test_sampling_is_checked_even_without_a_sample_count():
    # Without samples= there is no SamplingMethod element to build, but the
    # method name is still validated.
    with pytest.raises(ModelError, match="sampling"):
        model.forward_uq(observed=["v"], sampling="Sobol")
    with pytest.raises(ModelError, match="sampling"):
        model.validation(observed=["v"], sampling="Sobol")
    with pytest.raises(ModelError, match="sampling"):
        model.sensitivity_analysis(observed=["v"], sampling="Sobol")


def test_activity_builds_the_simulation_setting_inline():
    act = model.validation(
        observed=["v"], stop=10, step=0.1, tolerance=1e-6, method="cvode"
    )
    setting = act.simulation_setting
    assert (setting.stop_time, setting.interval) == (10.0, 0.1)
    assert (setting.tolerance, setting.method) == (1e-6, "cvode")
    assert type(setting.stop_time) is float  # the int 10 was coerced


def test_prebuilt_setting_conflicts_with_the_inline_fields():
    with pytest.raises(ModelError, match="setting"):
        model.validation(setting=model.simulation_setting(stop_time=1.0), stop=2.0)


def test_prebuilt_setting_is_used_as_is():
    setting = model.simulation_setting(stop_time=3.0, description="from the vendor")
    act = model.verification(observed=["v"], setting=setting)
    assert act.simulation_setting is setting


@pytest.mark.parametrize(
    "builder,cls",
    [
        ("validation", "ValidationType"),
        ("verification", "VerificationType"),
        ("sensitivity_analysis", "SensitivityAnalysisType"),
    ],
)
def test_sampled_activities_share_the_core(builder, cls):
    act = getattr(model, builder)(
        observed=["v"],
        uncertain=[
            model.uncertain_parameter("p", model.Uniform(minimum=0.0, maximum=1.0))
        ],
        samples=20,
        desired=model.desired_results(mean=True),
        domain_ref="ad1",
        id=f"{builder}1",
        name="an activity",
        description="built by the shared core",
    )
    assert type(act).__name__ == cls
    assert act.activity_domain_ref == "ad1"
    assert act.name == "an activity"
    assert act.desired_results.mean is True
    assert isinstance(model.sampling_of(act), model.LatinHypercubeType)


def test_calibration_has_targets_and_no_sampling():
    act = model.calibration(
        targets=[model.calibration_target("p", initial=1, lower=0, upper=2, unit="m")],
        reference=model.reference_data(["measured.csv"]),
        observed=["v"],
        id="cal1",
    )
    assert isinstance(act, model.CalibrationType)
    target = act.calibration_targets.target[0]
    assert (target.parameter_name, target.initial_value) == ("p", 1.0)
    assert (target.lower_bound, target.upper_bound, target.unit) == (0.0, 2.0, "m")
    assert act.reference_data.data_source[0].name == "measured.csv"
    assert not hasattr(act, "sampling_method")


def test_calibration_needs_at_least_one_target():
    with pytest.raises(ModelError, match="target"):
        model.calibration(targets=[])


# -- record builders --------------------------------------------------------


def test_desired_results_maps_the_short_names():
    dr = model.desired_results(
        mean=True, std=True, percentiles=[5, 50, 95], sobol_order=2, sobol_total=True
    )
    assert dr.mean is True
    assert dr.standard_deviation is True
    assert dr.percentiles.level == [5.0, 50.0, 95.0]
    # xs:double attributes are written as floats so that the XML says "5.0",
    # not "5", regardless of the input type.
    assert [type(level) for level in dr.percentiles.level] == [float] * 3
    assert (dr.sobol_indices.order, dr.sobol_indices.total) == (2, True)


def test_sobol_total_without_an_order_is_rejected():
    # SobolIndices/@order is required, so a lone sobol_total would vanish.
    with pytest.raises(ModelError, match="sobol_order"):
        model.desired_results(sobol_total=True)
    assert model.desired_results(sobol_order=1).sobol_indices.total is None


def test_reference_data_accepts_names_tuples_and_records():
    ref = model.reference_data(
        [
            "plain.csv",
            ("rig.csv", "resources/rig.csv"),
            model.DataSource(name="prebuilt.csv"),
        ],
        description="bench measurements",
    )
    assert [s.name for s in ref.data_source] == ["plain.csv", "rig.csv", "prebuilt.csv"]
    assert ref.data_source[1].file == "resources/rig.csv"
    assert ref.description == "bench measurements"


def test_error_metric_maps_passed_to_the_pass_attribute():
    metric = model.error_metric(
        "RMSE", 0.25, name="rmse", threshold=0.5, passed=True, observed_variable="v"
    )
    assert isinstance(metric, model.ErrorMetric)
    assert (metric.type_value, metric.value) == ("RMSE", 0.25)
    assert (metric.threshold, metric.pass_value) == (0.5, True)
    assert metric.observed_variable == "v"


def test_results_and_result_set_hide_the_choice_field():
    res = model.results(
        model.ResultsNormal(mu=1.0, sigma=0.5),
        model.error_metric("RMSE", 0.25),
        point="0.5",
    )
    rset = model.result_set(res)
    assert rset.results == [res]
    assert res.point == "0.5"
    doc = model.study("R", activities=[model.validation(observed=["v"], id="val1")])
    model.activity_of(doc, "val1").result_set = rset
    xml = serialize_study(doc).decode()
    assert '<uq:Normal mu="1.0" sigma="0.5"' in xml
    assert '<uq:ErrorMetric type="RMSE" value="0.25"' in xml
    assert parse_study(serialize_study(doc)) == doc


def test_domain_coverage_regions_and_classifications():
    cov = model.domain_coverage(
        "od1",
        "od2",
        regions=[
            ("Covered", model.hyper_rectangle([0], [1]), "the safe part"),
            (model.CoverageClassificationType.HIGH_RISK, model.convex_hull(TETRA)),
        ],
        id="cov1",
        description="gap analysis",
    )
    assert (cov.requested_domain_ref, cov.realized_domain_ref) == ("od1", "od2")
    first, second = cov.region
    assert first.classification is model.CoverageClassificationType.COVERED
    assert first.description == "the safe part"
    assert isinstance(model.shape_of(first), model.HyperRectangleType)
    assert second.classification is model.CoverageClassificationType.HIGH_RISK


def test_domain_coverage_rejects_unknown_classification():
    with pytest.raises(ModelError, match="classification"):
        model.domain_coverage("a", "b", regions=[("Maybe",)])


def test_assumption_coerces_values():
    # Asserted through the XML each value coercion produces: the test checks
    # which of the five value elements is written, not the internal compound
    # field it is stored in.
    doc = model.study("A")
    doc.required_assumptions = [
        model.required_assumptions(
            "ra1",
            [
                model.assumption("pressure", 101325, unit="Pa", id="as1"),
                model.assumption("temperature", (20, 40), unit="degC", id="as2"),
                model.assumption("terrain", "flat and dry", id="as3"),
                model.assumption("doc", model.StringValueType(value="flat"), id="as4"),
                model.assumption("nothing", id="as5"),
            ],
        )
    ]
    xml = serialize_study(doc).decode()
    assert '<uq:Real value="101325.0" unit="Pa"/>' in xml
    assert '<uq:RealRange low="20.0" high="40.0" unit="degC"/>' in xml
    assert "<uq:Text>flat and dry</uq:Text>" in xml
    assert '<uq:String value="flat"/>' in xml
    assert '<uq:Assumption id="as5" name="nothing"/>' in xml  # no value element
    assert parse_study(serialize_study(doc)) == doc


def test_assumption_rejects_unit_it_cannot_apply():
    with pytest.raises(ModelError, match="unit"):
        model.assumption("pressure", model.RealValueType(value=1.0), unit="Pa")
    with pytest.raises(ModelError, match="unit"):
        model.assumption("terrain", "flat", unit="m")
    with pytest.raises(ModelError, match="unit"):
        model.assumption("nothing", unit="m")


def test_assumption_origin_and_domain_refs():
    a = model.assumption(
        "road",
        "dry",
        id="as1",
        description="test track",
        origin="standard",
        domain_refs=["od1"],
    )
    assert a.origin is model.OriginType.STANDARD
    assert [r.ref for r in a.operational_domain_ref] == ["od1"]
    with pytest.raises(ModelError, match="origin"):
        model.assumption("road", "dry", origin="hearsay")


def test_required_assumptions_needs_one_assumption():
    ra = model.required_assumptions("ra1", [model.assumption("road", "dry")])
    assert ra.id == "ra1"
    with pytest.raises(ModelError, match="assumption"):
        model.required_assumptions("ra2", [])


# -- accessors --------------------------------------------------------------


def test_add_activity_creates_the_container_on_demand():
    doc = model.study("S")
    assert doc.activities is None
    act = model.add_activity(doc, model.forward_uq(observed=["v"]))
    assert model.activities_of(doc) == [act]
    model.add_activity(doc, model.validation(observed=["v"]))
    assert len(model.activities_of(doc)) == 2


def test_add_activity_rejects_non_activities():
    with pytest.raises(TypeError):
        model.add_activity(model.study("S"), model.AxesType())


def test_add_domain_creates_the_container_and_buckets_by_type():
    doc = model.study("S")
    od = model.operational_domain("od1", ["x"], model.hyper_rectangle([0], [1]))
    ad = model.activity_domain("ad1", ["x"], model.hyper_rectangle([0], [1]))
    model.add_domain(doc, od)
    model.add_domain(doc, ad)
    assert doc.domains.typed_operational_domain == [od]
    assert doc.domains.activity_domain == [ad]
    assert model.domains_of(doc) == [od, ad]
    assert model.find_domain(doc, "ad1") is ad
    assert model.find_domain(doc, "nope") is None


def test_upsert_coverage_replaces_by_id_then_appends():
    doc = model.study("S")
    first = model.domain_coverage("od1", "od2", regions=[("Covered",)], id="cov1")
    model.upsert_coverage(doc, first)
    replacement = model.domain_coverage(
        "od1", "od2", regions=[("HighRisk",)], id="cov1"
    )
    model.upsert_coverage(doc, replacement)
    assert doc.domains.domain_coverage == [replacement]
    other = model.domain_coverage("od1", "od3", regions=[("Covered",)], id="cov2")
    model.upsert_coverage(doc, other)
    assert doc.domains.domain_coverage == [replacement, other]


def test_activity_of_by_index_id_and_name():
    fuq = model.forward_uq(observed=["v"], id="fuq1")
    val = model.validation(observed=["v"], id="val1", name="DoV")
    doc = model.study("S", activities=[fuq, val])
    assert model.activity_of(doc) is fuq
    assert model.activity_of(doc, 1) is val
    assert model.activity_of(doc, "fuq1") is fuq
    assert model.activity_of(doc, "DoV") is val


def test_activity_of_reports_a_miss():
    doc = model.study("S", activities=[model.forward_uq(observed=["v"], id="fuq1")])
    with pytest.raises(ModelError, match="nope"):
        model.activity_of(doc, "nope")
    with pytest.raises(ModelError, match="3"):
        model.activity_of(doc, 3)
    with pytest.raises(ModelError, match="no activities"):
        model.activity_of(model.study("Empty"))


def test_observed_names_is_the_public_home_of_the_simulation_helper():
    from omuq import simulation

    assert simulation._observed_names is model.observed_names
    act = model.ForwardUncertaintyQuantificationType()
    with pytest.raises(SimulationError, match="ObservedVariables"):
        model.observed_names(act)
    act.observed_variables = model.ObservedVariablesType(source="vars.csv")
    with pytest.raises(SimulationError, match="externalized"):
        model.observed_names(act)
    act = model.forward_uq(observed=["a", "a"])
    with pytest.raises(SimulationError, match="duplicate"):
        model.observed_names(act)


def test_shape_of_accepts_boundaries_domains_and_shapes():
    hull = model.convex_hull(TETRA)
    dom = model.operational_domain("od1", ["x", "y", "z"], hull)
    assert model.shape_of(hull) is hull
    assert model.shape_of(dom.boundary) is hull
    assert model.shape_of(dom) is hull
    assert model.shape_of(model.BoundaryType()) is None
    assert model.shape_of(model.study("S")) is None


def test_study_accepts_domains_and_author():
    od = model.operational_domain("od1", ["x"], model.hyper_rectangle([0], [1]))
    doc = model.study("S", domains=[od], author="ab", info="i")
    assert doc.domains.typed_operational_domain == [od]
    assert doc.author == "ab"
    doc2 = model.study("S", domains=model.domains(od))
    assert doc2.domains.typed_operational_domain == [od]
    assert model.study("S", domains=[]).domains is None


def test_study_materializes_a_generator_of_activities():
    """Regression: study() used to iterate ``activities`` twice,
    once to validate and once via ``list(activities)``. A generator is
    exhausted by the first pass, so every activity was dropped, and
    ``if activities:`` did not catch it because a generator is always
    truthy.
    """
    act = model.forward_uq(observed=["v"], id="fuq1")
    doc = model.study("G", activities=(a for a in [act]))
    assert model.activities_of(doc) == [act]


def test_study_treats_an_exhausted_empty_generator_of_domains_as_none():
    """Regression: generators are always truthy, so
    ``if isinstance(domains, DomainsType) or domains:`` used to build an
    empty ``Domains`` element for an empty generator. An empty iterable is
    supposed to mean "no Domains element", as already held for a concrete
    empty list (see the test above).
    """
    doc = model.study("G", domains=(d for d in []))
    assert doc.domains is None


def test_all_is_explicit_and_leaks_nothing():
    assert isinstance(model.__all__, list)
    assert "annotations" not in model.__all__
    assert model.__all__ == sorted(set(model.__all__))
    for name in model.__all__:
        assert hasattr(model, name), name


def test_package_all_is_complete():
    """``omuq.__all__`` covers the SDK-wide public surface.

    Sibling to ``test_all_is_explicit_and_leaks_nothing`` above, but for the
    top-level package: every name in ``__all__`` must be importable, and the
    documented names (simulation, drivers, fitting, write-back, plus
    ``UqManager`` and ``DefaultExperiment``) must stay in it so a refactor
    cannot drop one unnoticed.
    """
    import omuq

    assert isinstance(omuq.__all__, list)
    for name in omuq.__all__:
        assert hasattr(omuq, name), name
    for name in (
        "UqManager",
        "Sink",
        "WebUi",
        "MemorySink",
        "PrintSink",
        "SkippedDomain",
        "FunctionDriver",
        "auto_driver",
        "fit_operational_domain",
        "fit_activity_domain",
        "fit_boundary",
        "samples_from_csv",
        "coverage_from_result",
        "RecordedResult",
        "ModelError",
        "FittingError",
        "DriverNotFoundError",
        "DefaultExperiment",
    ):
        assert name in omuq.__all__, name
        assert hasattr(omuq, name), name


# -- end to end -------------------------------------------------------------


def build_full_study() -> model.Study:
    """A study that uses every must-have builder at least once."""
    od = model.operational_domain(
        "od1",
        ["battery.V", "battery.I", "battery.T"],
        model.convex_hull(TETRA),
        name="Modeled OD",
        description="what the model covers",
    )
    requested = model.operational_domain(
        "od2",
        model.axes("battery.V", "battery.I", "battery.T", units={"battery.V": "V"}),
        model.hyper_rectangle([0, 0, 0], [1, 1, 1]),
        kind="RequestedOperationalDomain",
    )
    dov = model.activity_domain(
        "ad1",
        ["battery.V"],
        model.hyper_rectangle([0.0], [1.0]),
        domain_ref="od1",
        name="Domain of validation",
    )
    cov = model.domain_coverage(
        "od2",
        "od1",
        regions=[("HighRisk", model.hyper_rectangle([0.9], [1.0]), "extrapolation")],
        id="cov1",
    )
    uncertain = [
        model.uncertain_parameter(
            "battery.R0", model.Normal(mu=0.05, sigma=0.005), source="Measured"
        )
    ]
    doc = model.study(
        "FullStudy",
        activities=[
            model.forward_uq(
                uncertain=uncertain,
                observed=["battery.V"],
                samples=100,
                desired=model.desired_results(mean=True, percentiles=[5, 95]),
                stop=10,
                step=0.1,
                id="fuq1",
                domain_ref="ad1",
            ),
            model.validation(
                observed=["battery.V"],
                samples=50,
                sampling=model.Sampling.PSEUDO_RANDOM,
                reference=model.reference_data([("rig", "resources/rig.csv")]),
                id="val1",
                name="DoV",
            ),
            model.verification(observed=["battery.V"], samples=10, id="ver1"),
            model.sensitivity_analysis(
                observed=["battery.V"],
                samples=10,
                desired=model.desired_results(sobol_order=1, sobol_total=True),
                id="sa1",
            ),
            model.calibration(
                targets=[model.calibration_target("battery.R0", initial=0.05)],
                observed=["battery.V"],
                id="cal1",
            ),
        ],
        domains=[od, requested, dov, cov],
        author="omuq tests",
        info="every must-have builder",
    )
    doc.required_assumptions = [
        model.required_assumptions(
            "ra1",
            [
                model.assumption("ambient", (20, 40), unit="degC", id="as1"),
                model.assumption("terrain", "flat", id="as2"),
            ],
        )
    ]
    doc.model = model.model_info(
        name="battery",
        assumptions=model.modeling_assumptions(
            "ma1", [model.assumption("thermal", 300.0, unit="K", id="as3")]
        ),
    )
    val = model.activity_of(doc, "val1")
    val.result_set = model.result_set(
        model.results(
            model.ResultsNormal(mu=3.7, sigma=0.1),
            model.error_metric("RMSE", 0.25, threshold=0.5, passed=True),
        )
    )
    return doc


def test_full_study_attaches_validates_and_reopens_equal(pkg):
    doc = build_full_study()
    attached = pkg.uq.attach(doc, SsdRootAnchor())
    report = pkg.uq.validate(level=1)
    assert report.ok, str(report)

    pkg2, _ = reopen(pkg)
    (got,) = pkg2.uq.studies()
    assert got.document == attached.document


def test_full_study_coordinates_survive_serialization():
    doc = build_full_study()
    parsed = parse_study(serialize_study(doc))
    for before, after in zip(
        model.domains_of(doc), model.domains_of(parsed), strict=True
    ):
        assert model.points_of(before) == model.points_of(after)
    assert model.axis_names(model.find_domain(parsed, "od2")) == (
        "battery.V",
        "battery.I",
        "battery.T",
    )
