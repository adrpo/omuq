"""Fit a domain boundary to a cloud of observed points.

Replaces the offline hand computation documented in
``examples/screw_trajectory_domains.py``: convex hull of the measured
operating points, inflated about their centroid (whole run +25% for the
operational domain, early regime ``t <= 1.0`` +10% for the domain of
validation). :func:`fit_boundary` does the geometry;
:func:`fit_operational_domain` and :func:`fit_activity_domain` wrap it with
axes, an id and optional provenance to produce the same document objects as
:mod:`omuq.model`'s builders.

This module imports :mod:`omuq.model`, :mod:`omuq.errors` and
:mod:`omuq.geometry` only, never :mod:`omuq.simulation`, to avoid an import
cycle with the simulation layer. :data:`PointsLike` therefore accepts any
input with the right shape: objects with ``.time``/``.values`` (duck-typed;
:class:`omuq.simulation.Sample` qualifies), a ``name -> series`` mapping,
or plain coordinate tuples. :func:`samples_from_csv` imports ``Sample``
inside the function; see its docstring.

**Shapes.** ``shape="hull"`` fits a :class:`~omuq.model.ConvexHullType`
through the extreme points using scipy's ``ConvexHull``, imported lazily;
:func:`omuq.geometry.hull_unavailable_reason` supplies the same install
hint used by :mod:`omuq.geometry`. ``shape="box"`` fits an axis-aligned
:class:`~omuq.model.HyperRectangleType` in pure Python. ``shape="auto"``
tries the hull and falls back to the box only when scipy is missing or
Qhull rejects a degenerate (e.g. collinear or coplanar) point set. Any
other failure (too few points, a bad ``inflate``, ``pad`` on a hull)
raises.

**Inflation vs. padding.** ``inflate`` scales the fitted shape about a
center: the centroid of all input points by default, overridable via
``center=`` (hull only). A box scales each axis's half-width around its own
midpoint. ``pad`` adds a fixed absolute margin per axis instead, which is
the option to use for a zero-extent axis, where scaling a half-width of
zero changes nothing. ``pad`` is not supported for a hull: scaling vertices
about a center and offsetting a hull's faces by a fixed distance (a
Minkowski sum) are different operations.

**Precision.** ``precision`` significant digits is a relative resolution.
If a point cloud's extent is small next to its offset from the origin (an
absolute pressure, an encoder position in the millions), rounding to a
too-coarse ``precision`` can format two distinct corners or vertices to
the same string, collapsing an axis to zero extent, or leave the rounded
shape no longer containing the points it was fit from.
:func:`fit_boundary` checks both right after building the boundary: it
re-parses the formatted boundary and compares it against the unrounded
fit, using one quantization step of ``precision`` (see
:func:`_quantization_tol`) as the containment tolerance instead of the
checkers' ordinary ``tol=1e-9``. Raise ``precision`` if the check fails.

The guard's tolerance is the fit's own quantization step, which is
normally much looser than the default ``tol=1e-9`` of
:meth:`omuq.simulation.Simulation.monitor`. A zero-margin fit
(``inflate=0.0``, no ``pad``, the defaults) can therefore still reject
some of the samples it was fitted from when monitored later, because
formatting moves the boundary by up to one quantization step in either
direction. Pass a small ``inflate`` or ``pad``, or monitor with a matching
looser ``tol``, if a fit must stay violation-free against its own data
under later monitoring; see ``docs/SIMULATION.md`` section 5 ("Domain
monitoring semantics").
"""

from __future__ import annotations

import csv
import math
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, Protocol

from . import geometry, model
from .errors import FittingError, SimulationError

if TYPE_CHECKING:
    # Deferred: see the module docstring for why `Sample` cannot be a
    # module-scope import. `from __future__ import annotations` means this
    # branch is never executed at runtime, so it creates no cycle.
    from .simulation import Sample

#: Default significant-digit precision for coordinates written by this
#: module: the default of `fit_boundary` and of the `precision=` parameter
#: that `fit_operational_domain`/`fit_activity_domain` forward to both the
#: boundary fit and (when `keep_points=True`) the provenance points.
_DEFAULT_PRECISION = 6


class _SampleLike(Protocol):
    """What :func:`_extract_points` needs from a "Sample-like" object.

    Structural, not nominal: `omuq.simulation.Sample` satisfies this without
    either module knowing about the other's type.
    """

    time: float
    values: Mapping[str, float]


#: Accepted shapes for the ``data`` argument of :func:`fit_operational_domain`
#: and :func:`fit_activity_domain` - see the module docstring.
PointsLike = (
    Iterable[_SampleLike] | Mapping[str, Sequence[float]] | Iterable[Sequence[float]]
)

#: Approximation of XML's NCName production (letters/digits/``.``/``-``/
#: ``_``, not starting with a digit). Used to reject an id that would fail
#: schema validation (``xs:ID`` is NCName-typed) without a full
#: validate(level=1) round trip on every fit.
_NCNAME_RE = re.compile(r"^[A-Za-z_][\w.-]*$")


class _HullUnavailable(Exception):
    """Internal signal: a hull cannot be produced here.

    Raised only when scipy is missing or Qhull rejects a degenerate point
    set, never for a bad request (too few points, `inflate <= -1`, `pad`
    on a hull). `fit_boundary` catches this to degrade `shape="auto"` to a
    box, or re-raises it as a `FittingError` for an explicit
    `shape="hull"`. Every other `FittingError` raised while fitting a hull
    propagates through `shape="auto"` unchanged.
    """


# ---------------------------------------------------------------------------
# Small numeric helpers shared by the box and hull paths
# ---------------------------------------------------------------------------


def _to_float(value, *, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise FittingError(f"{where}: {value!r} is not a number") from exc


def _reject_non_finite(
    rows: Sequence[Sequence[float]], *, where: str = "fit_boundary()"
) -> None:
    for index, row in enumerate(rows):
        for pos, value in enumerate(row):
            if not math.isfinite(value):
                raise FittingError(
                    f"{where}: point {index + 1} has a non-finite coordinate "
                    f"at position {pos + 1}: {value!r}; NaN/inf cannot be "
                    "fitted into a boundary"
                )


def _fmt_point(row: Sequence[float], precision: int) -> str:
    """Coordinates formatted to ``precision`` significant digits."""
    return " ".join(f"{c:.{precision}g}" for c in row)


def _centroid(rows: Sequence[Sequence[float]]) -> tuple[float, ...]:
    dim = len(rows[0])
    n = len(rows)
    return tuple(sum(r[j] for r in rows) / n for j in range(dim))


def _coerce_center(center: Sequence[float], dim: int) -> tuple[float, ...]:
    row = tuple(_to_float(c, where="fit_boundary(): center") for c in center)
    if len(row) != dim:
        raise FittingError(
            f"fit_boundary(): center has {len(row)} coordinate(s), expected {dim}"
        )
    return row


def _is_zero_pad(pad: float | Sequence[float]) -> bool:
    if isinstance(pad, (int, float)):
        return float(pad) == 0.0
    return all(_to_float(p, where="fit_boundary(): pad") == 0.0 for p in pad)


def _pad_vector(pad: float | Sequence[float], dim: int) -> list[float]:
    if isinstance(pad, (int, float)):
        return [float(pad)] * dim
    vec = [_to_float(p, where="fit_boundary(): pad") for p in pad]
    if len(vec) != dim:
        raise FittingError(
            f"fit_boundary(): pad has {len(vec)} value(s), expected {dim} "
            "(one per axis) or a single scalar applied to every axis"
        )
    return vec


def _reject_string_point(point, *, index: int, where: str) -> None:
    """Reject a ``str`` standing in for a coordinate row.

    A string is iterable character by character, so without this check
    ``tuple(float(c) for c in "12")`` would succeed as the point ``(1.0,
    2.0)`` instead of failing. Mirrors :func:`omuq.model._point_rows`'s
    guard: same message shape, same :class:`TypeError`, since a string
    here is a type mistake rather than a domain-rule violation.
    """
    if isinstance(point, str):
        raise TypeError(
            f"{where}: point {index + 1} must be a sequence of numbers, "
            f"got the string {point!r}"
        )


def _check_inflate(inflate: float) -> None:
    # `not (inflate > -1.0)` (rather than `inflate <= -1.0`) also catches a
    # NaN inflate, which compares false either way.
    if not (inflate > -1.0):
        raise FittingError(
            f"fit_boundary(): inflate={inflate!r} must be greater than -1.0; "
            "a scale factor of (1 + inflate) <= 0 collapses or inverts the "
            "boundary. 0.0 leaves the size unchanged; negative values down "
            "to (but not including) -1.0 shrink it"
        )


# ---------------------------------------------------------------------------
# fit_boundary: box
# ---------------------------------------------------------------------------


def _fit_box(
    rows: Sequence[Sequence[float]],
    *,
    inflate: float,
    pad: float | Sequence[float],
    precision: int,
) -> model.BoundaryType:
    _check_inflate(inflate)
    dim = len(rows[0])
    pad_vec = _pad_vector(pad, dim)
    corner_lo: list[float] = []
    corner_hi: list[float] = []
    for j in range(dim):
        lo = min(r[j] for r in rows)
        hi = max(r[j] for r in rows)
        m = (lo + hi) / 2.0
        h = (hi - lo) / 2.0
        h_prime = h * (1.0 + inflate) + pad_vec[j]
        a, b = m - h_prime, m + h_prime
        # Canonical min/max per axis rather than trusting (a, b) to already
        # be ordered: a large negative pad on a near-zero-extent axis can
        # make h_prime negative, which would otherwise invert that axis.
        corner_lo.append(min(a, b))
        corner_hi.append(max(a, b))
    shape = model.HyperRectangleType(
        point=[
            model.HyperRectangleType.Point(
                coordinates=_fmt_point(corner_lo, precision)
            ),
            model.HyperRectangleType.Point(
                coordinates=_fmt_point(corner_hi, precision)
            ),
        ]
    )
    boundary = model.boundary(shape)
    pre_extents = [hi - lo for lo, hi in zip(corner_lo, corner_hi, strict=True)]
    exact_checker = geometry.RectChecker(
        [tuple(corner_lo), tuple(corner_hi)], where="fit_boundary()"
    )
    _check_precision(
        boundary,
        rows,
        pre_extents,
        precision=precision,
        shape_label="HyperRectangle",
        exact_checker=exact_checker,
    )
    return boundary


# ---------------------------------------------------------------------------
# fit_boundary: hull
# ---------------------------------------------------------------------------


def _fit_hull(
    rows: Sequence[Sequence[float]],
    *,
    inflate: float,
    pad: float | Sequence[float],
    center: Sequence[float] | None,
    precision: int,
) -> model.BoundaryType:
    _check_inflate(inflate)
    if not _is_zero_pad(pad):
        raise FittingError(
            "fit_boundary(): pad is not supported when fitting a ConvexHull "
            "(a Minkowski offset is not the same operation as scaling "
            "vertices about a center); use inflate= for a hull, or pass "
            "shape='box' if pad is what you need"
        )
    dim = len(rows[0])
    if len(rows) < dim + 1:
        raise FittingError(
            f"fit_boundary(): a ConvexHull over {dim} axes needs at least "
            f"{dim + 1} points, got {len(rows)}"
        )
    center_override = None if center is None else _coerce_center(center, dim)

    reason = geometry.hull_unavailable_reason()
    if reason is not None:
        raise _HullUnavailable(reason)
    import numpy
    from scipy.spatial import ConvexHull, QhullError

    try:
        hull = ConvexHull(numpy.asarray(rows, dtype=float))
    except QhullError as exc:
        raise _HullUnavailable(
            "Qhull rejected the point set (degenerate, e.g. collinear or "
            "coplanar); a full-dimensional point set is required for "
            "shape='hull' - try shape='box' instead"
        ) from exc

    c = _centroid(rows) if center_override is None else center_override
    vertices = [
        tuple(c[j] + (1.0 + inflate) * (rows[i][j] - c[j]) for j in range(dim))
        for i in hull.vertices
    ]
    shape = model.ConvexHullType(
        point=[
            model.ConvexHullType.Point(coordinates=_fmt_point(v, precision))
            for v in vertices
        ]
    )
    boundary = model.boundary(shape)
    pre_extents = [
        max(v[j] for v in vertices) - min(v[j] for v in vertices) for j in range(dim)
    ]
    try:
        exact_checker = geometry.HullChecker(vertices, where="fit_boundary()")
    except geometry.HullUnavailableError as exc:
        # Not expected: scipy availability was checked above. If it happens
        # anyway it is an environment gap, not a bad inflate, so re-raise
        # as the internal signal shape="auto" degrades on.
        raise _HullUnavailable(str(exc)) from exc
    except SimulationError as exc:
        # As inflate approaches -1 the transformed vertices shrink toward
        # a single point and can become numerically degenerate even though
        # the original hull (checked above) was fine. The cause is the
        # inflate parameter, not the environment, so shape="auto" must not
        # silently degrade to a box; raise a FittingError instead.
        raise FittingError(
            f"fit_boundary(): inflate={inflate!r} shrank the ConvexHull's "
            "vertices enough to make them numerically degenerate (too "
            "close to collinear/coplanar for Qhull to re-triangulate), "
            f"even though the original point set was fine ({exc}); use a "
            "less extreme inflate, or shape='box'"
        ) from exc
    _check_precision(
        boundary,
        rows,
        pre_extents,
        precision=precision,
        shape_label="ConvexHull",
        exact_checker=exact_checker,
    )
    return boundary


# ---------------------------------------------------------------------------
# fit_boundary: precision guard (shared by the box and hull paths)
# ---------------------------------------------------------------------------


def _quantization_tol(points: Sequence[Sequence[float]], precision: int) -> float:
    """One quantization step of ``points`` formatted to ``precision`` sig figs.

    ``f"{x:.{precision}g}"`` rounds each coordinate to nearest, so
    formatting moves any single coordinate by at most half of its own
    quantization step, ``10 ** (floor(log10(|x|)) - precision + 1)``.
    ``x == 0`` has no exponent and uses ``1e-9``, the checkers' default
    ``tol``. The return value is the full step, maximized over every
    coordinate of ``points``. Used as the containment tolerance in
    :func:`_check_precision`, it absorbs the worst-case rounding movement
    of any one coordinate while still catching a real loss of containment.
    """
    return max(
        1e-9 if x == 0.0 else 10.0 ** (math.floor(math.log10(abs(x))) - precision + 1)
        for row in points
        for x in row
    )


def _check_precision(
    boundary: model.BoundaryType,
    rows: Sequence[Sequence[float]],
    pre_extents: Sequence[float],
    *,
    precision: int,
    shape_label: str,
    exact_checker: geometry.RectChecker | geometry.HullChecker,
) -> None:
    """Reject a fit that formatting to ``precision`` significant digits broke.

    ``precision`` significant digits is a relative resolution: when a
    point cloud's extent is small next to its offset from the origin (an
    absolute pressure, an encoder position in the millions), rounding can
    format two distinct corners to the same string, collapsing an axis to
    zero extent, or shrink the shape so it no longer contains the points
    it was fit from. Both are checked here, right after formatting, by
    re-parsing the boundary and comparing it against the unrounded fit.
    ``pre_extents`` is the unrounded per-axis extent of the fitted shape;
    ``exact_checker`` tests containment against the unrounded shape, built
    from the numeric corners/vertices rather than a formatted string.

    An axis is flagged only when ``pre_extents`` says it had nonzero
    extent before formatting, so a legitimate zero-extent axis (no ``pad``
    given) is left alone. Containment is checked only for rows
    ``exact_checker`` itself contains: a negative ``inflate`` or an
    off-hull ``center=`` can fit a shape that never contained every input
    point, which is not a precision artifact. Only a row the unrounded fit
    contained but the formatted one does not counts as a rounding failure.
    The formatted side of the comparison needs a
    :func:`geometry.checker_for_boundary`, which for a hull needs scipy.
    If scipy is unavailable the containment check is skipped; if the
    rounded vertices are themselves degenerate (e.g. a collapsed axis
    Qhull would reject) a `FittingError` is raised. The axis-collapse
    check above runs either way.

    The formatted-side checker uses :func:`_quantization_tol` (one full
    quantization step, twice the worst-case rounding movement of any
    single coordinate) as its tolerance rather than the checkers' default
    ``tol=1e-9`` (sized for genuine geometry; see :mod:`omuq.geometry`).
    Formatting to ``precision`` significant digits routinely moves a face
    by far more than 1e-9 at everyday magnitudes (about 5e-6 at magnitude
    10 with precision=6), so a 1e-9 comparison flagged ordinary zero-slack
    fits depending on which way each corner rounded. Movement within one
    quantization step does not raise; a larger loss of containment (an
    intentional shrink, or ``precision`` too coarse for the data) does.
    ``exact_checker`` is built by the caller from the unrounded fit and
    keeps the ordinary ``tol=1e-9``.
    """
    remedy = f"pass a larger precision= (got precision={precision})"
    parsed = model.points_of(boundary)
    for j, extent in enumerate(pre_extents):
        if extent <= 0.0:
            continue
        lo = min(p[j] for p in parsed)
        hi = max(p[j] for p in parsed)
        if hi <= lo:
            raise FittingError(
                f"fit_boundary(): precision={precision} rounded axis "
                f"{j + 1} of the fitted {shape_label} down to zero extent "
                "(every formatted corner/vertex now reads the same value "
                f"on that axis, though the unrounded fit did not); {remedy}"
            )
    try:
        checker = geometry.checker_for_boundary(
            boundary,
            len(pre_extents),
            where="fit_boundary()",
            tol=_quantization_tol(parsed, precision),
        )
    except geometry.HullUnavailableError:
        # Cannot check a hull's containment without scipy; the axis-collapse
        # check above already caught the one symptom checkable without it.
        return
    except SimulationError as exc:
        raise FittingError(
            f"fit_boundary(): precision={precision} left the fitted "
            f"{shape_label} unusable ({exc}); {remedy}"
        ) from exc
    outside = [r for r in rows if exact_checker.contains(r) and not checker.contains(r)]
    if outside:
        raise FittingError(
            f"fit_boundary(): precision={precision} rounded the fitted "
            f"{shape_label} so tightly that it no longer contains all of "
            f"its own input points (e.g. {tuple(outside[0])!r} now falls "
            f"outside it); {remedy}"
        )


# ---------------------------------------------------------------------------
# fit_boundary
# ---------------------------------------------------------------------------


def _coerce_rows(points: Iterable[Sequence[float]]) -> list[tuple[float, ...]]:
    rows: list[tuple[float, ...]] = []
    for index, p in enumerate(points):
        _reject_string_point(p, index=index, where="fit_boundary()")
        try:
            row = tuple(float(c) for c in p)
        except (TypeError, ValueError) as exc:
            raise FittingError(
                f"fit_boundary(): point {index + 1} is not a sequence of numbers: {p!r}"
            ) from exc
        if not row:
            raise FittingError(f"fit_boundary(): point {index + 1} has no coordinates")
        if rows and len(row) != len(rows[0]):
            raise FittingError(
                f"fit_boundary(): point {index + 1} has {len(row)} "
                f"coordinate(s), expected {len(rows[0])}"
            )
        rows.append(row)
    if not rows:
        raise FittingError("fit_boundary(): at least one point is required")
    return rows


def fit_boundary(
    points: Iterable[Sequence[float]],
    *,
    shape: Literal["hull", "box", "auto"] = "hull",
    inflate: float = 0.0,
    pad: float | Sequence[float] = 0.0,
    center: Sequence[float] | None = None,
    precision: int = _DEFAULT_PRECISION,
) -> model.BoundaryType:
    """Fit a :class:`~omuq.model.BoundaryType` to a cloud of coordinate rows.

    ``shape``:

    * ``"hull"`` - the convex hull of the points (needs scipy), inflated
      about the centroid of all input points (``center=`` overrides it).
      ``pad`` is not supported (see the module docstring).
    * ``"box"`` - the axis-aligned bounding box, inflated per axis about its
      own midpoint, then offset by ``pad`` (a scalar for every axis, or one
      value per axis).
    * ``"auto"`` - tries ``"hull"``, degrading to ``"box"`` only when scipy
      is unavailable or Qhull rejects the point set as degenerate; every
      other rejection (too few points, bad ``inflate``, ``pad`` on a hull)
      still raises.

    ``inflate`` scales the shape about its center: ``v' = c + (1 + inflate)
    * (v - c)``. It must be greater than -1.0 (0.0 = unchanged; negative =
    shrink). Coordinates are written to ``precision`` significant digits.
    """
    rows = _coerce_rows(points)
    _reject_non_finite(rows)
    if shape == "hull":
        try:
            return _fit_hull(
                rows, inflate=inflate, pad=pad, center=center, precision=precision
            )
        except _HullUnavailable as exc:
            raise FittingError(f"fit_boundary(shape='hull'): {exc}") from exc
    if shape == "box":
        return _fit_box(rows, inflate=inflate, pad=pad, precision=precision)
    if shape == "auto":
        try:
            return _fit_hull(
                rows, inflate=inflate, pad=pad, center=center, precision=precision
            )
        except _HullUnavailable:
            return _fit_box(rows, inflate=inflate, pad=pad, precision=precision)
    raise FittingError(
        f"fit_boundary(): unknown shape={shape!r}; expected 'hull', 'box', or 'auto'"
    )


# ---------------------------------------------------------------------------
# Input normalization: PointsLike -> list[tuple[float, ...]]
# ---------------------------------------------------------------------------


def _in_window(t: float, window: tuple[float | None, float | None]) -> bool:
    lo, hi = window
    if lo is not None and t < lo:
        return False
    return not (hi is not None and t > hi)


def _missing_axes_error(
    missing: Sequence[str], available: Iterable[str], *, where: str
) -> FittingError:
    names = ", ".join(repr(n) for n in available) or "(none)"
    word = "axis" if len(missing) == 1 else "axes"
    bad = ", ".join(repr(m) for m in missing)
    return FittingError(
        f"{where}: {word} {bad} not found in the input; available names are {names}"
    )


def _points_from_samples(
    rows: Sequence[_SampleLike],
    axes: Sequence[str],
    *,
    time_window: tuple[float | None, float | None] | None,
) -> list[tuple[float, ...]]:
    points: list[tuple[float, ...]] = []
    for s in rows:
        t = _to_float(s.time, where="fit: sample .time")
        if time_window is not None and not _in_window(t, time_window):
            continue
        missing = [a for a in axes if a not in s.values]
        if missing:
            raise _missing_axes_error(missing, s.values, where="fit")
        points.append(tuple(_to_float(s.values[a], where="fit") for a in axes))
    return points


def _points_from_mapping(
    data: Mapping[str, Sequence[float]],
    axes: Sequence[str],
    *,
    time_window: tuple[float | None, float | None] | None,
) -> list[tuple[float, ...]]:
    lengths = {name: len(seq) for name, seq in data.items()}
    if len(set(lengths.values())) > 1:
        detail = ", ".join(f"{n}={n_len}" for n, n_len in lengths.items())
        raise FittingError(
            f"fit: mapping input has ragged series lengths ({detail}); every "
            "named series must have the same length"
        )
    missing = [a for a in axes if a not in data]
    if missing:
        raise _missing_axes_error(missing, data, where="fit")
    n = next(iter(lengths.values())) if lengths else 0
    times = None
    if time_window is not None:
        if "time" not in data:
            raise FittingError(
                "fit: time_window requires a 'time' key in the input mapping"
            )
        times = data["time"]
    points: list[tuple[float, ...]] = []
    for i in range(n):
        if times is not None:
            t = _to_float(times[i], where="fit: mapping 'time'")
            if not _in_window(t, time_window):
                continue
        points.append(tuple(_to_float(data[a][i], where="fit") for a in axes))
    return points


def _points_from_raw(
    rows: Sequence[Sequence[float]],
    axes: Sequence[str],
    *,
    time_window: tuple[float | None, float | None] | None,
) -> list[tuple[float, ...]]:
    if time_window is not None:
        raise FittingError(
            "fit: time_window requires Sample-like input (a .time attribute) "
            "or a mapping with a 'time' key; raw coordinate tuples carry no "
            "time information"
        )
    dim = len(axes)
    points: list[tuple[float, ...]] = []
    for index, row in enumerate(rows):
        _reject_string_point(row, index=index, where="fit")
        try:
            coords = tuple(float(c) for c in row)
        except (TypeError, ValueError) as exc:
            raise FittingError(
                f"fit: point {index + 1} is not a sequence of numbers: {row!r}"
            ) from exc
        if len(coords) != dim:
            raise FittingError(
                f"fit: point {index + 1} has {len(coords)} coordinate(s), "
                f"expected {dim} (len(axes)={dim})"
            )
        points.append(coords)
    return points


def _extract_points(
    data: PointsLike,
    axes: Sequence[str],
    *,
    time_window: tuple[float | None, float | None] | None = None,
) -> list[tuple[float, ...]]:
    """Normalize any :data:`PointsLike` input into coordinate rows.

    Dispatches on the shape of ``data`` (see the module docstring), then
    applies ``time_window`` and rejects non-finite coordinates before
    handing the result to :func:`fit_boundary`.
    """
    if isinstance(data, Mapping):
        points = _points_from_mapping(data, axes, time_window=time_window)
    else:
        rows = list(data)
        if rows and hasattr(rows[0], "values") and hasattr(rows[0], "time"):
            points = _points_from_samples(rows, axes, time_window=time_window)
        else:
            points = _points_from_raw(rows, axes, time_window=time_window)
    _reject_non_finite(points, where="fit")
    if not points:
        where = f" in time window {time_window}" if time_window is not None else ""
        raise FittingError(f"fit: no points{where} to fit a boundary from")
    return points


# ---------------------------------------------------------------------------
# Ids and refs
# ---------------------------------------------------------------------------


def _check_ncname(value: str, *, where: str) -> None:
    if not isinstance(value, str) or not _NCNAME_RE.match(value):
        raise FittingError(
            f"{where}: id={value!r} is not a valid NCName (xs:ID requires a "
            "name starting with a letter or underscore, followed only by "
            "letters, digits, '.', '-', or '_'); validate(level=1) would "
            "reject the document, so fitting refuses it now"
        )


def _ref_id(value, *, where: str) -> str | None:
    """Resolve ``parent=``/``domain=`` to a plain ref string, or ``None``."""
    if value is None or isinstance(value, str):
        return value
    ref = getattr(value, "id", None)
    if not ref:
        raise FittingError(
            f"{where}: the given domain object has no id; give it an id, or "
            "pass the ref as a plain string"
        )
    return ref


# ---------------------------------------------------------------------------
# Provenance: keep_points=True
# ---------------------------------------------------------------------------


def _experiment_points(
    points: Sequence[Sequence[float]], *, precision: int
) -> model.ExperimentPointsType:
    pts = model.PointsType(
        point=[
            model.PointsType.Point(coordinates=_fmt_point(p, precision)) for p in points
        ]
    )
    # No id on PointSet: guideline section 10 open point (see the brief);
    # nothing in the schema or the current guideline requires one.
    point_set = model.ExperimentPointsType.PointSet(points=pts)
    return model.ExperimentPointsType(point_set=[point_set])


# ---------------------------------------------------------------------------
# fit_operational_domain / fit_activity_domain
# ---------------------------------------------------------------------------


def fit_operational_domain(
    data: PointsLike,
    axes: Sequence[str],
    *,
    id: str,
    kind: model.TypedOperationalDomainKind
    | str = model.TypedOperationalDomainKind.MODELED_OPERATIONAL_DOMAIN,
    name: str | None = None,
    units: Mapping[str, str] | None = None,
    time_window: tuple[float | None, float | None] | None = None,
    shape: Literal["hull", "box", "auto"] = "hull",
    inflate: float = 0.0,
    pad: float | Sequence[float] = 0.0,
    precision: int = _DEFAULT_PRECISION,
    parent: model.TypedOperationalDomainType | str | None = None,
    keep_points: bool = False,
    description: str | None = None,
) -> model.TypedOperationalDomainType:
    """Fit a :class:`~omuq.model.TypedOperationalDomainType` from ``data``.

    ``data`` is any :data:`PointsLike` - Sample-like objects (e.g. a
    :class:`~omuq.simulation.MemorySink`'s ``.samples``), a ``name ->
    series`` mapping, or raw coordinate tuples - reduced to one point per
    row along ``axes`` (in that order), optionally restricted to
    ``time_window``. The boundary comes from :func:`fit_boundary`
    (``shape``/``inflate``/``pad``/``precision``; raise ``precision`` if it
    rejects the fit as rounded too coarse - see the module docstring).
    ``parent`` sets ``parentRef`` from a domain object's ``id`` or a plain
    ref string. ``keep_points=True`` records the (filtered) input points as
    ``ExperimentPoints`` provenance, written at the same ``precision``.

    Most rejections here raise :class:`~omuq.errors.FittingError`, but
    ``kind=``, ``units=``, and the other arguments forwarded straight
    through to :mod:`omuq.model`'s builders can instead raise
    :class:`~omuq.errors.ModelError` (also an
    :class:`~omuq.errors.OmuqError`) if the model layer itself rejects them
    - an unknown ``kind`` value, or ``units=`` naming an axis not in
    ``axes``.
    """
    _check_ncname(id, where="fit_operational_domain()")
    axes = tuple(axes)
    points = _extract_points(data, axes, time_window=time_window)
    boundary = fit_boundary(
        points, shape=shape, inflate=inflate, pad=pad, precision=precision
    )
    parent_ref = _ref_id(parent, where="fit_operational_domain()")
    domain = model.operational_domain(
        id,
        model.axes(*axes, units=units),
        boundary,
        kind=kind,
        name=name,
        description=description,
        parent_ref=parent_ref,
    )
    if keep_points:
        domain.experiment_points = _experiment_points(points, precision=precision)
    return domain


def fit_activity_domain(
    data: PointsLike,
    axes: Sequence[str],
    *,
    id: str,
    kind: str = "Validation",
    domain: model.TypedOperationalDomainType
    | model.ActivityDomainType
    | str
    | None = None,
    name: str | None = None,
    units: Mapping[str, str] | None = None,
    time_window: tuple[float | None, float | None] | None = None,
    shape: Literal["hull", "box", "auto"] = "hull",
    inflate: float = 0.0,
    pad: float | Sequence[float] = 0.0,
    precision: int = _DEFAULT_PRECISION,
    keep_points: bool = False,
    description: str | None = None,
) -> model.ActivityDomainType:
    """Fit an :class:`~omuq.model.ActivityDomainType` from ``data``.

    Same point handling and boundary fitting as
    :func:`fit_operational_domain` (including the ``precision`` fit-quality
    guard); ``domain`` sets ``domainRef`` from a domain object's ``id`` or a
    plain ref string (typically the modeled operational domain this
    activity domain narrows).

    Most rejections here raise :class:`~omuq.errors.FittingError`, but
    ``kind=``, ``units=``, and the other arguments forwarded straight
    through to :mod:`omuq.model`'s builders can instead raise
    :class:`~omuq.errors.ModelError` (also an
    :class:`~omuq.errors.OmuqError`) if the model layer itself rejects them
    - an unknown ``kind`` value, or ``units=`` naming an axis not in
    ``axes``.
    """
    _check_ncname(id, where="fit_activity_domain()")
    axes = tuple(axes)
    points = _extract_points(data, axes, time_window=time_window)
    boundary = fit_boundary(
        points, shape=shape, inflate=inflate, pad=pad, precision=precision
    )
    domain_ref = _ref_id(domain, where="fit_activity_domain()")
    dom = model.activity_domain(
        id,
        model.axes(*axes, units=units),
        boundary,
        kind=kind,
        name=name,
        domain_ref=domain_ref,
        description=description,
    )
    if keep_points:
        dom.experiment_points = _experiment_points(points, precision=precision)
    return dom


# ---------------------------------------------------------------------------
# samples_from_csv
# ---------------------------------------------------------------------------


def samples_from_csv(path: str | os.PathLike[str]) -> list[Sample]:
    """Read a CSV written by :class:`omuq.simulation.CsvSink` back into Samples.

    Expects the sink's exact format: header ``time,<name>,...``, one row per
    sample. Every returned :class:`~omuq.simulation.Sample` carries an empty
    ``violations`` tuple, since nothing was monitored while reading the
    file.

    ``Sample`` is imported inside this function because this module must
    not import :mod:`omuq.simulation` at module scope (see the module
    docstring): ``simulation.py`` may itself want to fit a domain from a
    run, which would create a cycle. The function-local import avoids the
    cycle while still returning real ``Sample`` objects rather than a
    parallel lookalike type.
    """
    from .simulation import Sample

    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                raise FittingError(
                    f"samples_from_csv({path!r}): file is empty"
                ) from None
            if not header or header[0] != "time":
                raise FittingError(
                    f"samples_from_csv({path!r}): expected a header starting "
                    f"with 'time', got {header!r}"
                )
            names = header[1:]
            samples: list[Sample] = []
            for line_no, row in enumerate(reader, start=2):
                if not row:
                    continue
                if len(row) != len(header):
                    raise FittingError(
                        f"samples_from_csv({path!r}): row {line_no} has "
                        f"{len(row)} field(s), expected {len(header)}"
                    )
                try:
                    time = float(row[0])
                    values = {n: float(v) for n, v in zip(names, row[1:], strict=True)}
                except ValueError as exc:
                    raise FittingError(
                        f"samples_from_csv({path!r}): row {line_no} is not "
                        f"numeric: {row!r}"
                    ) from exc
                samples.append(Sample(time=time, values=values, violations=()))
    except OSError as exc:
        raise FittingError(f"samples_from_csv({path!r}): {exc}") from exc
    return samples
