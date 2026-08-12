"""Domain fitting: turn a point cloud into a boundary, then a domain.

Covers the computation that used to live in
``examples/screw_trajectory_domains.py`` (convex hull of the measured
operating points, inflated about their centroid), now provided by
:mod:`omuq.fitting`. Every test either exercises the fitting math directly
(``fit_boundary``) or goes through the domain-level entry points
(``fit_operational_domain``, ``fit_activity_domain``) that add axes, ids
and provenance.
"""

import math
from types import SimpleNamespace

import pytest
from conftest import FakeDriver

from omuq import (
    CsvSink,
    FittingError,
    FunctionDriver,
    MemorySink,
    ModelError,
    Sample,
    Simulation,
    SsdRootAnchor,
    fit_activity_domain,
    fit_boundary,
    fit_operational_domain,
    geometry,
    model,
    parse_study,
    samples_from_csv,
    serialize_study,
)

# A square with an interior point: hull must keep exactly the 4 corners.
SQUARE_PLUS_INTERIOR = [
    (0.0, 0.0),
    (4.0, 0.0),
    (4.0, 4.0),
    (0.0, 4.0),
    (2.0, 2.0),
]
SQUARE_CORNERS = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
COLLINEAR_2D = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
# A generic small 2-D set: >= dim+1 = 3 points, usable for hull and box alike.
XY = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (0.0, 2.0)]
# A cloud whose extent (~3) is small relative to its offset from the origin
# (~1234568): the repro from the precision-guard finding. The default
# precision=6 is a relative resolution, so every x-coordinate rounds to the
# same 6-significant-digit string.
LARGE_OFFSET_TINY_EXTENT = [
    (1234567.8, 0.0),
    (1234570.2, 0.0),
    (1234569.0, 3.3),
    (1234568.4, -2.7),
]


# -- fit_boundary: box --------------------------------------------------


def test_box_inflation_exact_corners_on_a_square():
    boundary = fit_boundary(
        [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0), (2.0, 2.0)], shape="box", inflate=0.5
    )
    assert isinstance(model.shape_of(boundary), model.HyperRectangleType)
    assert model.points_of(boundary) == [(-0.5, -0.5), (2.5, 2.5)]


def test_box_pad_scalar_applies_to_every_axis():
    boundary = fit_boundary([(0.0, 0.0), (2.0, 4.0)], shape="box", pad=0.1)
    assert model.points_of(boundary) == [(-0.1, -0.1), (2.1, 4.1)]


def test_box_pad_per_axis():
    boundary = fit_boundary([(0.0, 0.0), (2.0, 4.0)], shape="box", pad=[0.1, 0.2])
    assert model.points_of(boundary) == [(-0.1, -0.2), (2.1, 4.2)]


def test_box_pad_wrong_length_raises():
    with pytest.raises(FittingError, match="pad"):
        fit_boundary([(0.0, 0.0), (2.0, 4.0)], shape="box", pad=[0.1, 0.2, 0.3])


@pytest.mark.parametrize("inflate", [-1.0, -1.5, -2.0])
def test_box_inflate_at_or_below_negative_one_raises(inflate):
    with pytest.raises(FittingError, match="inflate"):
        fit_boundary([(0.0,), (1.0,)], shape="box", inflate=inflate)


def test_box_inflate_just_above_negative_one_is_allowed():
    # Also checks that the precision guard (below) does not treat an
    # intentional shrink as a rounding artifact: the shrink excludes the
    # original input ((0.0,) and (2.0,) are both outside [0.5, 1.5]) and
    # the call must still succeed.
    boundary = fit_boundary([(0.0,), (2.0,)], shape="box", inflate=-0.5)
    assert model.points_of(boundary) == [(0.5,), (1.5,)]


def test_box_zero_extent_axis_needs_pad_to_become_non_degenerate():
    boundary = fit_boundary([(1.0, 0.0), (1.0, 2.0)], shape="box", pad=0.5)
    assert model.points_of(boundary) == [(0.5, -0.5), (1.5, 2.5)]


def test_box_needs_at_least_one_point():
    with pytest.raises(FittingError):
        fit_boundary([], shape="box")


# -- fit_boundary: hull (needs scipy) ------------------------------------


def test_hull_fit_contains_every_input_point():
    pytest.importorskip("scipy")
    boundary = fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull")
    checker = geometry.checker_for_boundary(boundary, 2, where="test")
    assert all(checker.contains(p) for p in SQUARE_PLUS_INTERIOR)


def test_hull_keeps_only_the_hull_vertices():
    pytest.importorskip("scipy")
    boundary = fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull")
    pts = model.points_of(boundary)
    assert len(pts) <= len(SQUARE_PLUS_INTERIOR)
    assert len(pts) == 4  # the interior point is not a vertex
    assert (2.0, 2.0) not in pts


def test_hull_inflated_strictly_contains_uninflated_extremes():
    pytest.importorskip("scipy")
    base = fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull")
    inflated = fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull", inflate=0.5)
    base_checker = geometry.checker_for_boundary(base, 2, where="base")
    inflated_checker = geometry.checker_for_boundary(inflated, 2, where="inflated")
    assert all(inflated_checker.contains(p) for p in SQUARE_CORNERS)
    # strictly bigger: the inflated hull's own vertices sit outside the base hull
    assert not all(base_checker.contains(v) for v in model.points_of(inflated))


def test_hull_center_override_produces_exact_vertex_set():
    pytest.importorskip("scipy")
    # v' = c + (1 + inflate) * (v - c) with c=(10, 10), inflate=1 (factor 2)
    # applied to the hull vertices of SQUARE_PLUS_INTERIOR: (0,0), (4,0),
    # (4,4), (0,4). The interior point (2, 2) is not a hull vertex. This
    # also checks that the precision guard does not treat an off-hull
    # center= (a fitted shape that does not contain the original input
    # cloud) as a rounding artifact: the call must still succeed.
    boundary = fit_boundary(
        SQUARE_PLUS_INTERIOR, shape="hull", inflate=1.0, center=(10.0, 10.0)
    )
    assert set(model.points_of(boundary)) == {
        (-10.0, -10.0),
        (-2.0, -10.0),
        (-2.0, -2.0),
        (-10.0, -2.0),
    }


def test_hull_center_dimension_mismatch_raises():
    with pytest.raises(FittingError, match="center"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull", center=(10.0, 10.0, 10.0))


def test_hull_centroid_uses_all_points_not_just_hull_vertices():
    pytest.importorskip("scipy")
    # The interior point (3, 3) is off-center, so it moves the centroid used
    # for inflation away from (2, 2), the centroid of the 4 hull vertices
    # alone. This fixture therefore detects an inflation wrongly centered on
    # the hull vertices only; SQUARE_PLUS_INTERIOR cannot, because its
    # interior point sits exactly at the hull-vertex centroid.
    points = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (3.0, 3.0)]
    boundary = fit_boundary(points, shape="hull", inflate=1.0)
    pts = model.points_of(boundary)
    # v' = c + 2*(v - c) with c = mean(all 5 points) = (2.2, 2.2);
    # the (0, 0) corner must map to (-2.2, -2.2), not (-2, -2) (which is
    # what a hull-vertices-only centroid of (2, 2) would produce).
    assert any(
        math.isclose(x, -2.2, abs_tol=1e-6) and math.isclose(y, -2.2, abs_tol=1e-6)
        for x, y in pts
    )


def test_hull_pad_is_rejected():
    with pytest.raises(FittingError, match="pad"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull", pad=0.1)


def test_hull_too_few_points_message_needs_no_scipy():
    # Mirrors geometry.HullChecker's own "at least dim+1" precheck, and (like
    # that one) must fail before ever attempting to import scipy.
    with pytest.raises(FittingError, match="at least 3"):
        fit_boundary([(0.0, 0.0), (1.0, 0.0)], shape="hull")


def test_hull_collinear_points_raise_suggesting_box():
    pytest.importorskip("scipy")
    with pytest.raises(FittingError, match="box"):
        fit_boundary(COLLINEAR_2D, shape="hull")


def test_hull_extreme_negative_inflate_raises_naming_inflate():
    # As inflate -> -1, the inflated (but unrounded) vertex cluster shrinks
    # toward a single point and can become degenerate enough that
    # re-triangulating it (for the exact_checker used by the precision
    # guard) raises QhullError, even though the original hull
    # (SQUARE_PLUS_INTERIOR) fit without error. This must surface as a
    # FittingError naming inflate as the cause, not a raw SimulationError
    # about the input points.
    pytest.importorskip("scipy")
    with pytest.raises(FittingError, match="inflate"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull", inflate=-0.999999999999999)


def test_hull_extreme_negative_inflate_auto_does_not_degrade_to_box():
    # A parameter-induced collapse (unlike a missing scipy or a degenerate
    # input point set) must not be downgraded to a box; this matches the
    # handling of pad on a hull under shape="auto".
    pytest.importorskip("scipy")
    with pytest.raises(FittingError, match="inflate"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="auto", inflate=-0.999999999999999)


def test_hull_scipy_absent_raises_with_install_hint(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    with pytest.raises(FittingError, match="no scipy here"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="hull")


# -- fit_boundary: auto ---------------------------------------------------


def test_auto_uses_hull_when_available():
    pytest.importorskip("scipy")
    boundary = fit_boundary(SQUARE_PLUS_INTERIOR, shape="auto")
    assert isinstance(model.shape_of(boundary), model.ConvexHullType)


def test_auto_degrades_to_box_on_collinear_points():
    pytest.importorskip("scipy")
    boundary = fit_boundary(COLLINEAR_2D, shape="auto")
    assert isinstance(model.shape_of(boundary), model.HyperRectangleType)


def test_auto_degrades_to_box_when_scipy_absent(monkeypatch):
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    boundary = fit_boundary(SQUARE_PLUS_INTERIOR, shape="auto")
    assert isinstance(model.shape_of(boundary), model.HyperRectangleType)
    assert model.points_of(boundary) == [(0.0, 0.0), (4.0, 4.0)]


def test_auto_does_not_degrade_a_pad_conflict():
    # pad!=0 with a hull attempt is a user error, not an environment gap, so
    # it must not be swallowed by auto's degrade-to-box behavior.
    with pytest.raises(FittingError, match="pad"):
        fit_boundary(SQUARE_PLUS_INTERIOR, shape="auto", pad=0.1)


# -- fit_boundary: generic input / degenerate cases ------------------------


def test_nan_coordinate_is_rejected():
    with pytest.raises(FittingError, match="non-finite"):
        fit_boundary([(0.0, 0.0), (1.0, float("nan")), (2.0, 1.0)], shape="box")


def test_inf_coordinate_is_rejected():
    with pytest.raises(FittingError, match="non-finite"):
        fit_boundary([(0.0, 0.0), (float("inf"), 1.0)], shape="box")


def test_ragged_points_raise():
    with pytest.raises(FittingError, match="coordinate"):
        fit_boundary([(0.0, 0.0), (1.0,)], shape="box")


def test_unknown_shape_raises():
    with pytest.raises(FittingError, match="shape"):
        fit_boundary(XY, shape="triangle")


def test_fit_boundary_rejects_a_string_standing_in_for_a_point():
    # A string is iterable character by character, so without a guard
    # tuple(float(c) for c in "12") would produce the point (1.0, 2.0)
    # instead of an error.
    with pytest.raises(TypeError, match="sequence of numbers"):
        fit_boundary(["12", "34"], shape="box")


def test_precision_controls_coordinate_formatting():
    # pad=0.05 keeps a safety margin so the low-precision rounding of the
    # corner does not also trip the "boundary must still contain its own
    # input" guard exercised in the precision-guard tests below.
    boundary = fit_boundary(
        [(0.0, 0.0), (1.0 / 3.0, 1.0)], shape="box", precision=3, pad=0.05
    )
    _lo, hi = model.points_of(boundary)
    assert hi[0] == pytest.approx(1.0 / 3.0 + 0.05, abs=1e-3)
    # 3 significant digits: 0.383, not 0.38333333333333336
    assert len(repr(hi[0]).replace("-", "").replace(".", "").lstrip("0")) <= 3


# -- fit_boundary: precision guard (formatting must not break the fit) -----
#
# `.6g` (the default) is a relative resolution: a point cloud whose extent
# is small next to its offset from the origin can have that extent rounded
# away entirely. These tests cover the precision guard (see the module
# docstring's "Precision" section) and the two ways the
# guard can observe the damage: an axis collapsing to zero extent (checkable
# without scipy, straight off the formatted vertex/corner strings) and a
# fitted shape that no longer contains points the unrounded fit did.
#
# LARGE_OFFSET_TINY_EXTENT's failures below are all axis-collapse: its
# large offset (~1.2e6) next to its small extent (~3) collapses an axis to
# zero extent at ordinary precision well before formatting noise on the
# contained corners could matter. The guard's containment tolerance is one
# formatting quantization step (_quantization_tol); anything tighter also
# fires on ordinary zero-slack fits (see
# test_precision_default_succeeds_on_ordinary_zero_slack_box below and its
# 3-D sibling). For a box, each face is one rounded coordinate, so the
# one-step bound is exact; for a hull, a face joins `dim` vertices and the
# bound is not proven in general. The axis-collapse branch is the guard's
# main check.


def test_precision_default_rejects_box_that_would_exclude_its_own_input():
    with pytest.raises(FittingError, match="precision"):
        fit_boundary(LARGE_OFFSET_TINY_EXTENT, shape="box", inflate=0.25)


def test_precision_default_rejects_hull_that_would_exclude_its_own_input():
    pytest.importorskip("scipy")
    with pytest.raises(FittingError, match="precision"):
        fit_boundary(LARGE_OFFSET_TINY_EXTENT, shape="hull", inflate=0.25)


def test_precision_twelve_succeeds_and_contains_all_inputs_box():
    boundary = fit_boundary(
        LARGE_OFFSET_TINY_EXTENT, shape="box", inflate=0.25, precision=12
    )
    checker = geometry.checker_for_boundary(boundary, 2, where="test")
    assert all(checker.contains(p) for p in LARGE_OFFSET_TINY_EXTENT)


def test_precision_twelve_succeeds_and_contains_all_inputs_hull():
    pytest.importorskip("scipy")
    boundary = fit_boundary(
        LARGE_OFFSET_TINY_EXTENT, shape="hull", inflate=0.25, precision=12
    )
    checker = geometry.checker_for_boundary(boundary, 2, where="test")
    assert all(checker.contains(p) for p in LARGE_OFFSET_TINY_EXTENT)


def test_precision_axis_collapse_detected_on_box_without_scipy(monkeypatch):
    # shape="box" never touches scipy, so the axis-collapse half of the
    # guard must still fire on a machine that cannot check hulls at all;
    # the guard must not depend on hull/scipy availability.
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    with pytest.raises(FittingError, match="precision"):
        fit_boundary(LARGE_OFFSET_TINY_EXTENT, shape="box", inflate=0.25)


def test_precision_axis_collapse_detected_when_auto_degrades_without_scipy(
    monkeypatch,
):
    # shape="auto" tries the hull first; with scipy unavailable it degrades
    # to a box, and that box fit must still be caught by the guard rather
    # than returned as a domain that rejects its own input.
    monkeypatch.setattr(geometry, "hull_unavailable_reason", lambda: "no scipy here")
    with pytest.raises(FittingError, match="precision"):
        fit_boundary(LARGE_OFFSET_TINY_EXTENT, shape="auto", inflate=0.25)


# O(10)-magnitude, non-round-number 3-D cloud, similar to a real simulation
# trace such as the zero-slack "run envelope" box
# examples/04_simulate_and_monitor.py fits from its samples.
CLOUD_3D_ORDINARY = [
    (12.345678, -3.456789, 45.678912),
    (18.234567, 7.891234, 22.345678),
    (9.876543, -8.765432, 38.123456),
    (15.111213, 2.222324, 50.505051),
    (10.999999, -1.000001, 33.333333),
]


def test_precision_default_succeeds_on_ordinary_zero_slack_box():
    # A zero-slack box loses a defining corner to nearest rounding on one
    # side or the other, so containment of the input points is only
    # guaranteed to one formatting quantization step (see _quantization_tol
    # and _check_precision's docstring); a tolerance like the checkers'
    # geometry tol=1e-9 is five orders of magnitude tighter than formatting
    # can guarantee. The guard must accept this point set at the default
    # precision.
    boundary = fit_boundary([(0.0, 0.0), (1.0 / 3.0, 1.0)], shape="box")
    # Containment is re-checked here at tol=1e-4, not the checkers' default
    # (1e-9): one quantization step at precision=6 for this data's
    # largest-magnitude coordinate (1.0) is 10**(0-6+1) = 1e-5, so 1e-4
    # gives an order of magnitude of headroom over it. That absorbs
    # formatting noise but still fails if the guard accepts an arbitrarily
    # large tolerance. tol=1e-9 is tighter than formatting can guarantee
    # and fails on this data.
    checker = geometry.checker_for_boundary(boundary, 2, where="test", tol=1e-4)
    assert checker.contains((0.0, 0.0))
    assert checker.contains((1.0 / 3.0, 1.0))


def test_precision_default_succeeds_on_ordinary_3d_zero_slack_box():
    # 3-D case: under a tol=1e-9 comparison this cloud excludes 2 of its 5
    # points, by ~1e-4 and ~2e-5 (ordinary formatting noise).
    boundary = fit_boundary(CLOUD_3D_ORDINARY, shape="box")
    # tol=1e-3: an order of magnitude over the ~1e-4 quantization step at
    # this cloud's largest magnitude (~50.5) and the default precision; see
    # the 2-D test above for the same reasoning.
    checker = geometry.checker_for_boundary(boundary, 3, where="test", tol=1e-3)
    assert all(checker.contains(p) for p in CLOUD_3D_ORDINARY)


def test_fit_operational_domain_precision_default_raises():
    with pytest.raises(FittingError, match="precision"):
        fit_operational_domain(
            LARGE_OFFSET_TINY_EXTENT, ["x", "y"], id="od", shape="box", inflate=0.25
        )


def test_fit_operational_domain_precision_param_forwarded():
    od = fit_operational_domain(
        LARGE_OFFSET_TINY_EXTENT,
        ["x", "y"],
        id="od",
        shape="box",
        inflate=0.25,
        precision=12,
    )
    checker = geometry.checker_for_boundary(od.boundary, 2, where="test")
    assert all(checker.contains(p) for p in LARGE_OFFSET_TINY_EXTENT)


def test_fit_activity_domain_precision_default_raises():
    with pytest.raises(FittingError, match="precision"):
        fit_activity_domain(
            LARGE_OFFSET_TINY_EXTENT, ["x", "y"], id="dov", shape="box", inflate=0.25
        )


def test_fit_activity_domain_precision_param_forwarded():
    dov = fit_activity_domain(
        LARGE_OFFSET_TINY_EXTENT,
        ["x", "y"],
        id="dov",
        shape="box",
        inflate=0.25,
        precision=12,
    )
    checker = geometry.checker_for_boundary(dov.boundary, 2, where="test")
    assert all(checker.contains(p) for p in LARGE_OFFSET_TINY_EXTENT)


# -- input normalization: raw coordinate tuples ----------------------------


def test_raw_tuples_arity_mismatch_raises():
    with pytest.raises(FittingError, match="coordinate"):
        fit_operational_domain([(0.0, 1.0, 2.0)], ["a", "b"], id="od", shape="box")


def test_raw_tuples_reject_a_string_standing_in_for_a_point():
    # Same guard as fit_boundary's own _coerce_rows, ported into the raw
    # tuple path (_points_from_raw) used by fit_operational_domain and
    # fit_activity_domain.
    with pytest.raises(TypeError, match="sequence of numbers"):
        fit_operational_domain(["12", "34"], ["x", "y"], id="od", shape="box")


def test_raw_tuples_reject_time_window():
    with pytest.raises(FittingError, match="time"):
        fit_operational_domain(
            [(0.0, 1.0), (2.0, 3.0)],
            ["a", "b"],
            id="od",
            shape="box",
            time_window=(0.0, 1.0),
        )


# -- input normalization: mapping name -> series ---------------------------


def test_mapping_input_builds_points_in_axis_order():
    data = {"a": [0.0, 2.0, 4.0], "b": [1.0, 3.0, 0.0]}
    od = fit_operational_domain(data, ["a", "b"], id="od", shape="box")
    assert model.points_of(od) == [(0.0, 0.0), (4.0, 3.0)]


def test_mapping_input_ragged_lengths_raises():
    data = {"a": [0.0, 1.0, 2.0], "b": [0.0, 1.0]}
    with pytest.raises(FittingError, match="ragged"):
        fit_operational_domain(data, ["a", "b"], id="od", shape="box")


def test_mapping_input_time_window_without_time_key_raises():
    data = {"a": [0.0, 1.0], "b": [0.0, 1.0]}
    with pytest.raises(FittingError, match="time"):
        fit_operational_domain(
            data, ["a", "b"], id="od", shape="box", time_window=(None, 1.0)
        )


def test_mapping_input_time_window_filters_rows():
    data = {"time": [0.0, 0.5, 1.0, 1.5], "a": [0.0, 1.0, 2.0, 3.0]}
    od = fit_operational_domain(
        data, ["a"], id="od", shape="box", time_window=(None, 1.0)
    )
    assert model.points_of(od) == [(0.0,), (2.0,)]


def test_mapping_input_missing_axis_lists_available_names():
    data = {"a": [0.0, 1.0], "b": [0.0, 1.0]}
    with pytest.raises(FittingError) as excinfo:
        fit_operational_domain(data, ["a", "c"], id="od", shape="box")
    msg = str(excinfo.value)
    assert "'c'" in msg
    assert "'a'" in msg and "'b'" in msg


# -- input normalization: Sample-like objects ------------------------------


def test_sample_like_axes_subset_and_reordered():
    samples = [
        Sample(time=0.0, values={"b": 1.0, "a": 0.0, "c": 9.0}),
        Sample(time=1.0, values={"b": 3.0, "a": 2.0, "c": 9.0}),
        Sample(time=2.0, values={"b": 0.0, "a": 4.0, "c": 9.0}),
    ]
    od = fit_operational_domain(samples, ["a", "b"], id="od", shape="box")
    assert model.points_of(od) == [(0.0, 0.0), (4.0, 3.0)]


def test_sample_like_time_window_keeps_the_early_regime():
    samples = [
        Sample(time=0.0, values={"a": 0.0}),
        Sample(time=0.5, values={"a": 1.0}),
        Sample(time=1.0, values={"a": 2.0}),
        Sample(time=1.5, values={"a": 3.0}),
    ]
    od = fit_operational_domain(
        samples, ["a"], id="od", shape="box", time_window=(None, 1.0)
    )
    assert model.points_of(od) == [(0.0,), (2.0,)]


def test_sample_like_missing_axis_lists_available_names():
    samples = [Sample(time=0.0, values={"a": 0.0, "b": 1.0})]
    with pytest.raises(FittingError) as excinfo:
        fit_operational_domain(samples, ["a", "c"], id="od", shape="box")
    msg = str(excinfo.value)
    assert "'c'" in msg
    assert "'a'" in msg and "'b'" in msg


def test_empty_points_after_time_window_raises():
    samples = [Sample(time=5.0, values={"a": 0.0})]
    with pytest.raises(FittingError, match="no points"):
        fit_operational_domain(
            samples, ["a"], id="od", shape="box", time_window=(None, 1.0)
        )


# -- fit_operational_domain / fit_activity_domain: model output -----------


def test_fit_operational_domain_attaches_and_validates_l1(pkg):
    pytest.importorskip("scipy")
    od = fit_operational_domain(SQUARE_PLUS_INTERIOR, ["x", "y"], id="od")
    assert od.geometry_kind == "ConvexHull"
    study = model.study("FitStudy", domains=[od])
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=1)
    assert report.ok, str(report)


def test_fit_operational_domain_box_sets_geometry_kind():
    od = fit_operational_domain(XY, ["x", "y"], id="od", shape="box")
    assert od.geometry_kind == "HyperRectangle"


def test_fit_activity_domain_with_domain_object_sets_ref_and_passes_l2(pkg):
    # shape="box" throughout: this test is about domain_ref/L2, not hull
    # geometry, so it must not depend on scipy being installed.
    od = fit_operational_domain(SQUARE_PLUS_INTERIOR, ["x", "y"], id="od", shape="box")
    dov = fit_activity_domain(XY, ["x", "y"], id="dov", domain=od, shape="box")
    assert dov.domain_ref == "od"
    study = model.study("FitStudy", domains=[od, dov])
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert report.ok, str(report)


def test_fit_activity_domain_domain_accepts_a_plain_string_ref():
    dov = fit_activity_domain(XY, ["x", "y"], id="dov", domain="elsewhere", shape="box")
    assert dov.domain_ref == "elsewhere"


def test_fit_activity_domain_domain_object_without_id_raises():
    bad = SimpleNamespace(id=None)
    with pytest.raises(FittingError, match="id"):
        fit_activity_domain(XY, ["x", "y"], id="dov", domain=bad, shape="box")


def test_fit_operational_domain_parent_accepts_object_and_string():
    base = fit_operational_domain(XY, ["x", "y"], id="base", shape="box")
    child = fit_operational_domain(XY, ["x", "y"], id="child", shape="box", parent=base)
    assert child.parent_ref == "base"
    child2 = fit_operational_domain(
        XY, ["x", "y"], id="child2", shape="box", parent="literalRef"
    )
    assert child2.parent_ref == "literalRef"


def test_fit_operational_domain_rejects_a_bad_ncname_id():
    with pytest.raises(FittingError, match="NCName"):
        fit_operational_domain(XY, ["x", "y"], id="1bad", shape="box")


def test_fit_activity_domain_rejects_a_bad_ncname_id():
    with pytest.raises(FittingError, match="NCName"):
        fit_activity_domain(XY, ["x", "y"], id="bad id", shape="box")


def test_fit_operational_domain_forwards_units_name_description_kind():
    od = fit_operational_domain(
        XY,
        ["x", "y"],
        id="od",
        shape="box",
        units={"x": "m", "y": "s"},
        name="My OD",
        description="an operational domain",
        kind=model.TypedOperationalDomainKind.REQUESTED_OPERATIONAL_DOMAIN,
    )
    assert od.name == "My OD"
    assert od.description == "an operational domain"
    assert od.kind == model.TypedOperationalDomainKind.REQUESTED_OPERATIONAL_DOMAIN
    assert {a.name: a.unit for a in od.axes.axis} == {"x": "m", "y": "s"}


def test_fit_activity_domain_forwards_units_name_description_kind():
    dov = fit_activity_domain(
        XY,
        ["x", "y"],
        id="dov",
        shape="box",
        units={"x": "m", "y": "s"},
        name="My DoV",
        description="a domain of validation",
        kind="Calibration",
    )
    assert dov.name == "My DoV"
    assert dov.description == "a domain of validation"
    assert dov.kind == "Calibration"
    assert {a.name: a.unit for a in dov.axes.axis} == {"x": "m", "y": "s"}


def test_fit_operational_domain_kind_forwarding_error_surfaces_as_model_error():
    # kind= is forwarded straight through to model.operational_domain(),
    # which validates it as a TypedOperationalDomainKind -- rejection is a
    # ModelError, not a FittingError (see the fit_operational_domain
    # docstring).
    with pytest.raises(ModelError):
        fit_operational_domain(XY, ["x", "y"], id="od", shape="box", kind="NotAKind")


def test_fit_activity_domain_units_forwarding_error_surfaces_as_model_error():
    # units= is forwarded straight through to model.axes(), which rejects a
    # unit naming an axis that isn't in axes -- a ModelError, not a
    # FittingError.
    with pytest.raises(ModelError):
        fit_activity_domain(
            XY, ["x", "y"], id="dov", shape="box", units={"not_an_axis": "m"}
        )


def test_keep_points_records_provenance_and_round_trips():
    od = fit_operational_domain(
        SQUARE_PLUS_INTERIOR, ["x", "y"], id="od", shape="box", keep_points=True
    )
    assert od.experiment_points is not None
    point_set = od.experiment_points.point_set[0]
    assert point_set.id is None  # guideline section 10 open point: no PointSet/@id
    assert len(point_set.points.point) == len(SQUARE_PLUS_INTERIOR)

    doc = model.study("FitStudy", domains=[od])
    parsed = parse_study(serialize_study(doc))
    got = model.find_domain(parsed, "od")
    assert len(got.experiment_points.point_set[0].points.point) == len(
        SQUARE_PLUS_INTERIOR
    )


def test_keep_points_defaults_to_false():
    od = fit_operational_domain(XY, ["x", "y"], id="od", shape="box")
    assert od.experiment_points is None


# -- samples_from_csv -------------------------------------------------------


def test_samples_from_csv_reads_back_csv_sink_output(tmp_path):
    out = tmp_path / "run.csv"
    sim = Simulation(FakeDriver(), ["a", "b"], stop=1.0, step=0.5)
    sim.subscribe(CsvSink(out))
    sim.run()

    samples = samples_from_csv(out)
    assert [s.time for s in samples] == [0.0, 0.5, 1.0]
    assert samples[0].values == {"a": 0.0, "b": 10.0}
    assert samples[1].values == {"a": 0.5, "b": 10.5}
    assert all(s.violations == () for s in samples)
    assert all(isinstance(s, Sample) for s in samples)


def test_samples_from_csv_round_trips_into_a_fit(tmp_path):
    out = tmp_path / "run.csv"
    sim = Simulation(FakeDriver(), ["a", "b"], stop=1.0, step=0.5)
    sim.subscribe(CsvSink(out))
    sim.run()

    samples = samples_from_csv(out)
    od = fit_operational_domain(samples, ["a", "b"], id="od", shape="box")
    assert model.points_of(od) == [(0.0, 10.0), (1.0, 11.0)]


def test_samples_from_csv_missing_file_raises(tmp_path):
    with pytest.raises(FittingError):
        samples_from_csv(tmp_path / "nope.csv")


# -- end-to-end invariant ----------------------------------------------------


def test_fit_from_a_run_then_monitor_the_same_run_has_zero_violations():
    pytest.importorskip("scipy")

    def fn(t):
        return {"a": math.sin(t), "b": math.cos(t)}

    sink = MemorySink()
    sim1 = Simulation(FunctionDriver(fn), ["a", "b"], stop=2.0, step=0.1)
    sim1.subscribe(sink)
    sim1.run()

    od = fit_operational_domain(sink.samples, ["a", "b"], id="od", inflate=0.25)

    sim2 = Simulation(FunctionDriver(fn), ["a", "b"], stop=2.0, step=0.1)
    sim2.monitor(od)
    result = sim2.run()
    assert result.ok
    assert result.samples_outside == {"od": 0}
