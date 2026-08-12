import csv
import io
import math
import warnings

import pytest
from conftest import (
    FakeDriver,
    hull_boundary,
    make_activity,
    make_study,
    op_domain,
    rect_boundary,
    rect_domain,
    reopen,
    study_with_domains,
)

from omuq import (
    CsvSink,
    DockerOMSimulatorDriver,
    FunctionDriver,
    MemorySink,
    OMSimulatorDriver,
    PrintSink,
    Simulation,
    SimulationError,
    SkippedDomain,
    SsdRootAnchor,
    geometry,
    model,
)
from omuq.geometry import HullChecker, RectChecker, checker_for_boundary
from omuq.model import observed_names

# -- fakes -----------------------------------------------------------------


class RecordingSink:
    def __init__(self):
        self.events = []

    def on_start(self, names):
        self.events.append(("start", tuple(names)))

    def on_sample(self, sample):
        self.events.append(("sample", sample))

    def on_finish(self):
        self.events.append(("finish",))


# -- runner basics ---------------------------------------------------------


def test_run_dispatches_samples_in_order():
    seen = []
    sim = Simulation(FakeDriver(), ["a", "b"], stop=2.0, step=0.5)
    sim.subscribe(seen.append)
    result = sim.run()
    assert [s.time for s in seen] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert all(list(s.values) == ["a", "b"] for s in seen)
    assert seen[2].values == {"a": 1.0, "b": 11.0}
    assert result.steps == 4
    assert result.end_time == 2.0
    assert result.names == ("a", "b")
    assert result.samples_outside == {}


def test_driver_lifecycle_calls():
    drv = FakeDriver()
    Simulation(drv, ["a", "b"], stop=2.0, step=0.5).run()
    assert drv.calls[0] == ("initialize", 0.0, 2.0, 0.5, ("a", "b"))
    assert drv.calls[-1] == ("terminate",)
    assert sum(1 for c in drv.calls if c[0] == "initialize") == 1
    assert sum(1 for c in drv.calls if c[0] == "terminate") == 1
    assert [c[1] for c in drv.calls if c[0] == "advance"] == [0.5, 1.0, 1.5, 2.0]
    assert sum(1 for c in drv.calls if c[0] == "read") == 5


def test_explicit_step_stop_win_over_setting():
    act = make_activity(interval=0.1, stop_time=10.0)
    drv = FakeDriver()
    Simulation.for_activity(act, drv, step=0.5, stop=1.0).run()
    assert drv.calls[0] == ("initialize", 0.0, 1.0, 0.5, ("a", "b"))


def test_fallback_to_simulation_setting():
    act = make_activity(interval=0.25, stop_time=1.0)
    drv = FakeDriver()
    result = Simulation.for_activity(act, drv).run()
    assert drv.calls[0] == ("initialize", 0.0, 1.0, 0.25, ("a", "b"))
    assert result.steps == 4


@pytest.mark.parametrize("with_setting", [False, True])
def test_missing_step_raises(with_setting):
    act = make_activity(stop_time=1.0, with_setting=with_setting)
    with pytest.raises(SimulationError, match="interval"):
        Simulation.for_activity(act, FakeDriver())


@pytest.mark.parametrize("with_setting", [False, True])
def test_missing_stop_raises(with_setting):
    act = make_activity(interval=0.1, with_setting=with_setting)
    step = None if with_setting else 0.1  # step resolves first; supply it here
    with pytest.raises(SimulationError, match="stopTime"):
        Simulation.for_activity(act, FakeDriver(), step=step)


@pytest.mark.parametrize("step,stop", [(0.0, 1.0), (-1.0, 1.0), (0.1, 0.0)])
def test_invalid_step_and_stop_raise(step, stop):
    with pytest.raises(SimulationError):
        Simulation(FakeDriver(), ["a"], stop=stop, step=step)


def test_observed_names_from_activity():
    act = make_activity(observed=("x.y", "z"), interval=0.5, stop_time=1.0)
    drv = FakeDriver()
    Simulation.for_activity(act, drv).run()
    assert drv.calls[0][4] == ("x.y", "z")


def test_no_observed_variables_raises():
    act = model.ForwardUncertaintyQuantificationType()
    with pytest.raises(SimulationError, match="ObservedVariables"):
        observed_names(act)
    act.observed_variables = model.ObservedVariablesType()
    with pytest.raises(SimulationError, match="ObservedVariables"):
        observed_names(act)


def test_externalized_observed_variables_raises():
    act = model.ForwardUncertaintyQuantificationType(
        observed_variables=model.ObservedVariablesType(source="vars.csv")
    )
    with pytest.raises(SimulationError, match="externalized"):
        observed_names(act)


def test_duplicate_observed_name_raises():
    act = make_activity(observed=("a", "a"), interval=0.5, stop_time=1.0)
    with pytest.raises(SimulationError, match="duplicate"):
        Simulation.for_activity(act, FakeDriver())


def test_sink_lifecycle_order():
    sink = RecordingSink()
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5)
    sim.subscribe(sink)
    sim.run()
    kinds = [e[0] for e in sink.events]
    assert kinds == ["start", "sample", "sample", "sample", "finish"]
    assert sink.events[0] == ("start", ("a",))


def test_csv_sink_writes_header_and_rows(tmp_path):
    out = tmp_path / "out.csv"
    sim = Simulation(FakeDriver(), ["a", "b"], stop=1.0, step=0.5)
    sim.subscribe(CsvSink(out))
    sim.run()
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["time", "a", "b"]
    assert len(rows) == 4
    assert [float(v) for v in rows[2]] == [0.5, 0.5, 10.5]


def test_terminate_and_finish_on_mid_run_error():
    drv = FakeDriver()
    sink = RecordingSink()
    sim = Simulation(drv, ["a"], stop=1.0, step=0.25)
    sim.subscribe(sink)

    def boom(sample):
        if sample.time >= 0.5:
            raise RuntimeError("subscriber exploded")

    sim.subscribe(boom)
    with pytest.raises(RuntimeError, match="subscriber exploded"):
        sim.run()
    assert ("terminate",) in drv.calls
    assert sink.events[-1] == ("finish",)


def test_partial_final_step_clamps_to_stop():
    seen = []
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.4)
    sim.subscribe(seen.append)
    result = sim.run()
    assert [s.time for s in seen] == [0.0, 0.4, 0.8, 1.0]
    assert result.steps == 3


def test_float_noise_grid_has_no_extra_step():
    seen = []
    sim = Simulation(FakeDriver(), ["a"], stop=0.3, step=0.1)
    sim.subscribe(seen.append)
    sim.run()
    assert len(seen) == 4


def test_run_twice_raises():
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5)
    sim.run()
    with pytest.raises(SimulationError, match="already run"):
        sim.run()


def test_subscribe_rejects_non_callable():
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5)
    with pytest.raises(TypeError):
        sim.subscribe(object())


# -- geometry --------------------------------------------------------------


def test_rect_checker_contains_and_corner_order():
    box = RectChecker([(1.0, 5.0), (0.0, 3.0)], where="d")
    assert box.contains((0.5, 4.0))
    assert box.contains((0.0, 3.0))
    assert box.contains((1.0 + 1e-12, 5.0))
    assert not box.contains((1.5, 4.0))
    assert not box.contains((0.5, 2.0))


def test_rect_checker_needs_two_corners():
    with pytest.raises(SimulationError, match="exactly 2"):
        RectChecker([(0.0, 0.0)], where="d")


def test_hull_checker_triangle_2d():
    pytest.importorskip("scipy")
    tri = HullChecker([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], where="d")
    assert tri.contains((0.2, 0.2))
    assert tri.contains((0.5, 0.5))  # on the hypotenuse
    assert not tri.contains((0.6, 0.6))
    assert not tri.contains((-0.1, 0.5))


def test_hull_checker_tetrahedron_3d():
    pytest.importorskip("scipy")
    tet = HullChecker(
        [(0.2, 0.2, 0.2), (0.8, 0.2, 0.2), (0.5, 0.8, 0.2), (0.5, 0.5, 0.8)],
        where="dov",
    )
    assert tet.contains((0.5, 0.4, 0.3))
    assert not tet.contains((0.5, 0.4, 0.9))
    assert not tet.contains((0.0, 0.0, 0.0))


def test_hull_min_points_error_before_scipy():
    # 2 points in 3D: must fail without needing scipy.
    with pytest.raises(SimulationError, match="at least 4"):
        HullChecker([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], where="operationalDomain")


def test_hull_degenerate_points_error():
    pytest.importorskip("scipy")
    coplanar = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)]
    with pytest.raises(SimulationError, match="degenerate"):
        HullChecker(coplanar, where="flat")


def test_hull_unavailable_reason_reflects_scipy_and_is_cached():
    reason = geometry.hull_unavailable_reason()
    assert reason is geometry.hull_unavailable_reason()  # one attempt, then cached
    try:
        import scipy.spatial  # noqa: F401
    except ImportError:
        assert reason is not None and "pip install scipy" in reason
    else:
        assert reason is None


def test_hull_checker_raises_the_unavailable_reason(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    with pytest.raises(SimulationError, match="no scipy here"):
        HullChecker([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], where="d")


def test_checker_for_boundary_errors():
    with pytest.raises(SimulationError, match="no ConvexHull or HyperRectangle"):
        checker_for_boundary(None, 2, where="d")
    with pytest.raises(SimulationError, match="no ConvexHull or HyperRectangle"):
        checker_for_boundary(model.BoundaryType(), 2, where="d")
    bad = hull_boundary([(0.1, 0.2)])
    model.shape_of(bad).point[0].coordinates = "0.1 oops"
    with pytest.raises(SimulationError, match="unparsable"):
        checker_for_boundary(bad, 2, where="d")
    with pytest.raises(SimulationError, match="declares 3 axes"):
        checker_for_boundary(rect_boundary((0.0, 0.0), (1.0, 1.0)), 3, where="d")


# -- domain monitoring -----------------------------------------------------


def test_monitor_rect_domain_reports_violations():
    act = make_activity(observed=("a",), interval=0.25, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())  # a in [0, 0.25]
    seen = []
    sim.on_violation(seen.append)
    result = sim.run()
    assert result.samples_outside == {"dov": 3}
    assert [v.time for v in seen] == [0.5, 0.75, 1.0]
    v = seen[0]
    assert v.domain_id == "dov"
    assert v.domain_kind == "Validation"
    assert v.names == ("a",)
    assert v.point == (0.5,)
    assert "outside Validation domain 'dov'" in str(v)


def test_sample_carries_violations():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())
    samples = []
    sim.subscribe(samples.append)
    sim.run()
    assert [len(s.violations) for s in samples] == [0, 1, 1]


def test_violation_filter_by_kind_and_id():
    act = make_activity(observed=("a",), interval=0.25, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain(id="dov", hi=(0.25,)))  # violated at 0.5, 0.75, 1.0
    sim.monitor(op_domain("od", ("a",), (0.0,), (0.6,)))  # violated at 0.75, 1.0
    all_v, by_kind, by_id, by_od_kind = [], [], [], []
    sim.on_violation(all_v.append)
    sim.on_violation(by_kind.append, only="Validation")
    sim.on_violation(by_id.append, only="od")
    sim.on_violation(by_od_kind.append, only="ModeledOperationalDomain")
    result = sim.run()
    assert result.samples_outside == {"dov": 3, "od": 2}
    assert len(all_v) == 5
    assert [v.domain_id for v in by_kind] == ["dov", "dov", "dov"]
    assert [v.time for v in by_id] == [0.75, 1.0]
    assert [v.domain_id for v in by_od_kind] == ["od", "od"]


def test_monitor_axes_not_observed_raises():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    with pytest.raises(SimulationError, match="not observed variables.*p"):
        sim.monitor(rect_domain(names=("p",)))


def test_monitor_requires_axes():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    dom = model.ActivityDomainType(
        id="noaxes", kind="Validation", boundary=rect_boundary((0.0,), (1.0,))
    )
    with pytest.raises(SimulationError, match="no Axes"):
        sim.monitor(dom)


def test_for_study_monitors_and_skips():
    study = study_with_domains(bare=True)
    sim = Simulation.for_study(study, FakeDriver())
    result = sim.run()
    assert result.samples_outside == {"od": 0, "dov": 3}
    skipped = dict(result.skipped_domains)
    assert set(skipped) == {"paramDomain", "bare"}
    assert "someParameter" in skipped["paramDomain"]
    assert "boundary" in skipped["bare"]


def test_for_study_raises_on_too_few_hull_points():
    act = make_activity(observed=("a", "b", "c"), interval=0.5, stop_time=1.0)
    study = model.study(
        "Bad",
        activities=[act],
        domains=[
            model.operational_domain(
                "od",
                ("a", "b", "c"),
                model.convex_hull([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]),
            )
        ],
    )
    with pytest.raises(SimulationError, match="at least 4"):
        Simulation.for_study(study, FakeDriver())


def test_for_study_without_activities_raises():
    study = model.study("Empty")
    with pytest.raises(SimulationError, match="no activities"):
        Simulation.for_study(study, FakeDriver())


def test_for_study_activity_by_id_and_name():
    study = model.study(
        "TwoActivities",
        activities=[
            make_activity(observed=("a",), interval=0.5, stop_time=1.0),
            model.validation(
                observed=["b"], step=0.5, stop=1.0, id="second", name="Val"
            ),
        ],
    )
    for key in ("second", "Val", 1):
        drv = FakeDriver()
        Simulation.for_study(study, drv, activity=key).run()
        assert drv.calls[0][4] == ("b",)


def test_for_study_unknown_activity_raises_simulation_error():
    study = model.study(
        "One", activities=[make_activity(observed=("a",), interval=0.5, stop_time=1.0)]
    )
    with pytest.raises(SimulationError, match="nope"):
        Simulation.for_study(study, FakeDriver(), activity="nope")


def test_hull_domain_is_skipped_when_hull_checking_is_unavailable(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    study = model.study(
        "HullStudy",
        activities=[make_activity(observed=("a", "b"), interval=0.5, stop_time=1.0)],
        domains=[
            model.operational_domain(
                "od",
                ("a", "b"),
                model.convex_hull(
                    [(-1.0, -1.0), (100.0, -1.0), (-1.0, 100.0), (100.0, 100.0)]
                ),
            )
        ],
    )
    result = Simulation.for_study(study, FakeDriver()).run()
    assert result.monitored_domains == ()
    assert result.skipped_domains == (SkippedDomain("od", "no scipy here"),)
    assert result.ok
    assert result.steps == 2


def test_monitor_still_raises_when_hull_checking_is_unavailable(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    act = make_activity(observed=("a", "b"), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    domain = model.operational_domain(
        "od",
        ("a", "b"),
        model.convex_hull([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]),
    )
    with pytest.raises(SimulationError, match="no scipy here"):
        sim.monitor(domain)


def test_for_study_still_raises_on_bad_hull_data_without_scipy(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    study = model.study(
        "Bad",
        activities=[
            make_activity(observed=("a", "b", "c"), interval=0.5, stop_time=1.0)
        ],
        domains=[
            model.operational_domain(
                "od",
                ("a", "b", "c"),
                model.convex_hull([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]),
            )
        ],
    )
    with pytest.raises(SimulationError, match="at least 4"):
        Simulation.for_study(study, FakeDriver())


# -- result surface --------------------------------------------------------


def test_skipped_domain_is_a_named_pair():
    result = Simulation.for_study(study_with_domains(bare=True), FakeDriver()).run()
    skipped = result.skipped_domains[0]
    assert isinstance(skipped, SkippedDomain)
    assert skipped.domain_id == "paramDomain"
    assert "someParameter" in skipped.reason
    domain_id, reason = skipped  # still unpacks like the old 2-tuple
    assert (domain_id, reason) == (skipped.domain_id, skipped.reason)


def test_exits_count_excursions_not_samples():
    # sin(2*pi*t) leaves [-0.5, 0.5] twice over one period.
    sim = Simulation(
        FunctionDriver(lambda t: [math.sin(2 * math.pi * t)]),
        ["a"],
        stop=1.0,
        step=0.05,
    )
    sim.monitor(rect_domain(id="box", lo=(-0.5,), hi=(0.5,)))
    result = sim.run()
    assert result.exits == {"box": 2}
    assert result.samples_outside == {"box": 14}
    assert len(result.violations) == 14
    assert [v.time for v in result.violations] == sorted(
        v.time for v in result.violations
    )
    assert not result.ok


def test_result_ok_and_violations_of():
    act = make_activity(observed=("a",), interval=0.25, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain(id="dov", hi=(0.25,)))  # violated at 0.5, 0.75, 1.0
    sim.monitor(op_domain("od", ("a",), (0.0,), (0.6,)))  # violated at 0.75, 1.0
    result = sim.run()
    assert not result.ok
    assert result.monitored_domains == ("dov", "od")
    assert [v.time for v in result.violations_of("dov")] == [0.5, 0.75, 1.0]
    assert [v.time for v in result.violations_of("ModeledOperationalDomain")] == [
        0.75,
        1.0,
    ]
    assert len(result.violations_of(["dov", "od"])) == 5
    assert result.violations_of("nothing") == ()


def test_result_ok_without_violations():
    result = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5).run()
    assert result.ok
    assert result.violations == ()
    assert result.exits == {}
    assert result.monitored_domains == ()


def test_summary_lists_monitored_and_skipped_domains():
    result = Simulation.for_study(study_with_domains(bare=True), FakeDriver()).run()
    text = result.summary()
    assert str(result) == text
    assert "4 steps" in text
    assert "t=1" in text
    assert "od: inside throughout" in text
    assert "dov: 3 samples outside in 1 excursion" in text
    assert "first exit t=0.5" in text
    assert "paramDomain" in text and "someParameter" in text
    assert "bare" in text


# -- sinks -----------------------------------------------------------------


def test_memory_sink_keeps_samples_and_resets_between_runs():
    sink = MemorySink()
    assert sink.names is None and sink.samples == []
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5)
    sim.subscribe(sink)
    sim.run()
    assert sink.names == ("a",)
    assert [s.time for s in sink.samples] == [0.0, 0.5, 1.0]
    again = Simulation(FakeDriver(), ["b", "c"], stop=0.5, step=0.5)
    again.subscribe(sink)
    again.run()
    assert sink.names == ("b", "c")
    assert [s.time for s in sink.samples] == [0.0, 0.5]


def test_print_sink_throttles_and_marks_violations(capsys):
    act = make_activity(observed=("a",), interval=0.25, stop_time=1.5)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())  # a in [0, 0.25]
    sim.subscribe(PrintSink(every=3))
    sim.run()
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == ["t=0", "t=0.75", "t=1.5"]
    assert "a=0.75" in lines[1]
    assert "[!dov]" in lines[1] and "[!dov]" in lines[2]
    assert "[!" not in lines[0]


def test_print_sink_writes_to_a_file_and_rejects_a_zero_interval():
    buf = io.StringIO()
    sim = Simulation(FakeDriver(), ["a"], stop=1.0, step=0.5)
    sim.subscribe(PrintSink(file=buf, precision=2))
    sim.run()
    assert buf.getvalue().splitlines() == ["t=0  a=0", "t=0.5  a=0.5", "t=1  a=1"]
    with pytest.raises(SimulationError, match="every"):
        PrintSink(every=0)


# -- violation subscriptions -----------------------------------------------


def test_only_filter_that_matches_nothing_warns_at_run():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())
    sim.on_violation(lambda v: None, only="Validaton")  # typo
    with pytest.warns(UserWarning, match="Validaton"):
        sim.run()


def test_empty_only_filter_warns_at_run():
    # only=[] mutes the subscriber just as a typo does (usually via an
    # empty selection list), so it must warn too.
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())
    seen = []
    sim.on_violation(seen.append, only=[])
    with pytest.warns(UserWarning, match="no monitored domain"):
        sim.run()
    assert seen == []


def test_matching_only_filter_does_not_warn():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())
    sim.on_violation(lambda v: None, only=("Validation", "dov"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sim.run()


# -- OMSimulatorDriver (in-process adapter, fully faked) -------------------


class _BaseFakeModel:
    def __init__(self):
        self.calls = []
        self.t = 0.0
        self.step = 0.0

    def setStopTime(self, t):
        self.calls.append(("setStopTime", t))

    def setFixedStepSize(self, h):
        self.calls.append(("setFixedStepSize", h))
        self.step = h

    def initialize(self):
        self.calls.append(("initialize",))

    def getValue(self, ref):
        self.calls.append(("getValue", ref))
        return self.t + 100.0

    def terminate(self):
        self.calls.append(("terminate",))

    def delete(self):
        self.calls.append(("delete",))


class StepUntilModel(_BaseFakeModel):
    def stepUntil(self, t):
        self.calls.append(("stepUntil", t))
        self.t = t

    def doStep(self):
        self.calls.append(("doStep",))


class DoStepModel(_BaseFakeModel):
    def doStep(self):
        self.calls.append(("doStep",))
        self.t += self.step


class NoStepperModel(_BaseFakeModel):
    pass


def _factory(record):
    def cref(name):
        record.append(name)
        return ("sys", *name.split("."))

    return cref


def test_omsim_prefers_stepuntil():
    m = StepUntilModel()
    d = OMSimulatorDriver(m, cref_factory=_factory([]))
    d.initialize(0.0, 1.0, 0.5, ["a"])
    d.advance(0.5)
    assert ("stepUntil", 0.5) in m.calls
    assert not any(c[0] == "doStep" for c in m.calls)


def test_omsim_falls_back_to_dostep():
    m = DoStepModel()
    d = OMSimulatorDriver(m, cref_factory=_factory([]))
    d.initialize(0.0, 1.0, 0.5, ["a"])
    d.advance(0.5)
    d.advance(1.0)
    assert sum(1 for c in m.calls if c[0] == "doStep") == 2
    assert m.t == pytest.approx(1.0)


def test_omsim_no_stepper_raises_with_attr_listing():
    d = OMSimulatorDriver(NoStepperModel(), cref_factory=_factory([]))
    with pytest.raises(SimulationError, match="getValue"):
        d.initialize(0.0, 1.0, 0.5, ["a"])


def test_omsim_setter_probe_order():
    m = StepUntilModel()
    d = OMSimulatorDriver(m, cref_factory=_factory([]))
    d.initialize(0.0, 2.0, 0.1, ["a"])
    assert m.calls.index(("setStopTime", 2.0)) < m.calls.index(("initialize",))
    assert m.calls.index(("setFixedStepSize", 0.1)) < m.calls.index(("initialize",))


def test_omsim_cref_mapping_and_caching():
    record = []
    m = StepUntilModel()
    d = OMSimulatorDriver(m, cref_factory=_factory(record))
    d.initialize(0.0, 1.0, 0.5, ["comp.v", "w"])
    assert record == ["comp.v", "w"]
    d.read(["comp.v", "w"])
    d.read(["comp.v", "w"])
    assert record == ["comp.v", "w"]  # cached, factory not called again
    ref = next(c[1] for c in m.calls if c[0] == "getValue")
    assert ref == ("sys", "comp", "v")


def test_omsim_missing_package_raises_helpful():
    try:
        import OMSimulator  # noqa: F401

        pytest.skip("OMSimulator is installed")
    except ImportError:
        pass
    d = OMSimulatorDriver(StepUntilModel())
    with pytest.raises(SimulationError, match="cref_factory"):
        d.initialize(0.0, 1.0, 0.5, ["a"])


def test_omsim_terminate_never_deletes():
    m = StepUntilModel()
    d = OMSimulatorDriver(m, cref_factory=_factory([]))
    d.initialize(0.0, 1.0, 0.5, ["a"])
    d.terminate()
    assert ("terminate",) in m.calls
    assert not any(c[0] == "delete" for c in m.calls)


def test_omsim_end_to_end_with_simulation(tmp_path):
    m = StepUntilModel()
    d = OMSimulatorDriver(m, cref_factory=_factory([]))
    act = make_activity(observed=("x",), interval=0.5, stop_time=1.0)
    out = tmp_path / "run.csv"
    sim = Simulation.for_activity(act, d)
    sim.subscribe(CsvSink(out))
    result = sim.run()
    assert result.steps == 2
    with open(out, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["time", "x"]
    assert [float(r[1]) for r in rows[1:]] == [100.0, 100.5, 101.0]


# -- DockerOMSimulatorDriver (via a local fake runner subprocess) ----------


def test_docker_driver_streams_through_simulation(fake_runner):
    seen = []
    sim = Simulation(fake_runner(), ["a", "b"], stop=1.0, step=0.25)
    sim.subscribe(seen.append)
    result = sim.run()
    assert [s.time for s in seen] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert seen[2].values == {"a": 0.5, "b": 10.5}
    assert result.steps == 4


def test_docker_driver_missing_handshake(fake_runner):
    with pytest.raises(SimulationError, match="handshake"):
        Simulation(fake_runner("no-handshake"), ["a"], stop=1.0, step=0.5).run()


def test_docker_driver_skips_pre_handshake_noise(fake_runner):
    seen = []
    sim = Simulation(fake_runner("noisy"), ["a"], stop=0.5, step=0.25)
    sim.subscribe(seen.append)
    sim.run()
    assert [s.time for s in seen] == [0.0, 0.25, 0.5]


def test_docker_driver_time_grid_divergence(fake_runner):
    with pytest.raises(SimulationError, match="diverged"):
        Simulation(fake_runner("diverge"), ["a"], stop=1.0, step=0.25).run()


def test_docker_driver_runner_death_reports_stderr(fake_runner):
    with pytest.raises(SimulationError, match="solver exploded"):
        Simulation(fake_runner("die"), ["a"], stop=2.0, step=0.25).run()


def test_docker_driver_terminate_kills_process(fake_runner):
    drv = fake_runner()
    drv.initialize(0.0, 1000.0, 0.5, ["a"])
    proc = drv._proc
    assert proc is not None
    drv.terminate()
    assert proc.poll() is not None
    drv.terminate()  # idempotent


def test_docker_driver_missing_ssp(tmp_path):
    drv = DockerOMSimulatorDriver(tmp_path / "nope.ssp", command=["true"])
    with pytest.raises(SimulationError, match="not found"):
        drv.initialize(0.0, 1.0, 0.5, ["a"])


def test_docker_argv_construction(tmp_path):
    ssp = tmp_path / "m.ssp"
    ssp.write_bytes(b"x")
    missing = tmp_path / "no-such-docker"
    drv = DockerOMSimulatorDriver(
        ssp, image="img", system="sys", platform="linux/amd64", docker=str(missing)
    )
    with pytest.raises(SimulationError, match="cannot start"):
        drv.initialize(0.0, 1.0, 0.5, ["x.y", "z"])
    argv = drv.argv
    assert argv[:4] == [str(missing), "run", "--rm", "-i"]
    assert argv[4:6] == ["--platform", "linux/amd64"]
    assert argv[6:8] == ["-v", f"{ssp.parent.resolve()}:/data:ro"]
    assert argv[8] == "img"
    job = dict(zip(argv[9::2], argv[10::2], strict=False))
    assert job["--ssp"] == "/data/m.ssp"
    assert job["--system"] == "sys"
    assert job["--names"] == "x.y,z"


# -- builder ---------------------------------------------------------------


def test_simulation_setting_builder_roundtrips(pkg):
    study = make_study("SimSetting")
    model.activity_of(study).simulation_setting = model.simulation_setting(
        stop_time=2.0, interval=0.1, tolerance=1e-6, method="cvode"
    )
    pkg.uq.attach(study, SsdRootAnchor())
    assert pkg.uq.validate(level=1).ok
    pkg2, _ = reopen(pkg)
    setting = model.activity_of(pkg2.uq.study().document).simulation_setting
    assert setting.stop_time == 2.0
    assert setting.interval == 0.1
    assert setting.tolerance == 1e-6
    assert setting.method == "cvode"
