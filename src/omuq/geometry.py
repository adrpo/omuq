"""Point-in-boundary tests for omuq domain geometry.

``HyperRectangle`` containment is pure python. ``ConvexHull`` containment
uses scipy's Qhull bindings, an optional dependency imported lazily when a
hull checker is first constructed; without scipy, construction raises
:class:`HullUnavailableError` with an install hint.

:class:`HullUnavailableError` is distinct from the other geometry errors
because it indicates a missing dependency, not a problem with the
document. :meth:`omuq.Simulation.for_study` catches it and records the
domain as skipped, while a broken point set (too few points, ragged
coordinates, a degenerate hull) still raises.

Checkers are built once per monitored domain (precomputing the hull's
halfspace equations) and then evaluated once per sample.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence

from .errors import SimulationError
from .model import BoundaryType, HyperRectangleType, shape_of

#: Error message used when scipy is not installed.
_SCIPY_HINT = (
    "checking ConvexHull boundaries requires scipy; install it with "
    "'pip install scipy' (or the 'omuq[geometry]' extra)"
)


class HullUnavailableError(SimulationError):
    """ConvexHull checking is unavailable here (see the module docstring)."""


@functools.cache
def hull_unavailable_reason() -> str | None:
    """Why ConvexHull boundaries cannot be checked here, or ``None``.

    A single import attempt, cached for the life of the process. Called by
    :class:`HullChecker` for its error message and by ``for_study`` for
    its skip reason.
    """
    try:
        import scipy.spatial  # noqa: F401
    except ImportError:
        return _SCIPY_HINT
    return None


def parse_points(points, *, where: str) -> list[tuple[float, ...]]:
    """Parse ``Point.coordinates`` strings into float tuples.

    ``where`` names the owning domain in error messages.
    """
    parsed: list[tuple[float, ...]] = []
    for index, point in enumerate(points):
        try:
            coords = tuple(float(c) for c in point.coordinates.split())
        except ValueError as exc:
            raise SimulationError(
                f"domain {where!r}: point {index + 1} has unparsable "
                f"coordinates {point.coordinates!r}"
            ) from exc
        if parsed and len(coords) != len(parsed[0]):
            raise SimulationError(
                f"domain {where!r}: point {index + 1} has {len(coords)} "
                f"coordinate(s), expected {len(parsed[0])}"
            )
        parsed.append(coords)
    return parsed


class RectChecker:
    """Axis-aligned box from the two corner points of a HyperRectangle."""

    def __init__(
        self,
        corners: Sequence[tuple[float, ...]],
        *,
        where: str,
        tol: float = 1e-9,
    ):
        if len(corners) != 2:
            raise SimulationError(
                f"domain {where!r}: a HyperRectangle needs exactly 2 corner "
                f"points, got {len(corners)}"
            )
        first, second = corners
        self._lo = tuple(min(a, b) for a, b in zip(first, second, strict=False))
        self._hi = tuple(max(a, b) for a, b in zip(first, second, strict=False))
        self._tol = tol

    def contains(self, point: Sequence[float]) -> bool:
        return all(
            lo - self._tol <= x <= hi + self._tol
            for x, lo, hi in zip(point, self._lo, self._hi, strict=False)
        )


class HullChecker:
    """Convex-hull membership via Qhull halfspace equations (needs scipy)."""

    def __init__(
        self,
        vertices: Sequence[tuple[float, ...]],
        *,
        where: str,
        tol: float = 1e-9,
    ):
        if not vertices:
            raise SimulationError(f"domain {where!r}: ConvexHull has no points")
        dim = len(vertices[0])
        if len(vertices) < dim + 1:
            raise SimulationError(
                f"domain {where!r}: a ConvexHull over {dim} axes needs at "
                f"least {dim + 1} points, got {len(vertices)}"
            )
        # The point-set checks above run first, so a broken document is
        # reported even when scipy is missing.
        reason = hull_unavailable_reason()
        if reason is not None:
            raise HullUnavailableError(reason)
        try:
            import numpy
            from scipy.spatial import ConvexHull, QhullError
        except ImportError as exc:  # pragma: no cover - scipy just imported
            raise HullUnavailableError(_SCIPY_HINT) from exc
        try:
            hull = ConvexHull(numpy.asarray(vertices, dtype=float))
        except QhullError as exc:
            raise SimulationError(
                f"domain {where!r}: Qhull rejected the ConvexHull points "
                "(degenerate set, e.g. collinear or coplanar); a "
                "full-dimensional point set is required"
            ) from exc
        self._numpy = numpy
        self._normals = hull.equations[:, :-1]
        self._offsets = hull.equations[:, -1]
        self._tol = tol

    def contains(self, point: Sequence[float]) -> bool:
        x = self._numpy.asarray(point, dtype=float)
        return bool((self._normals @ x + self._offsets <= self._tol).all())


def checker_for_boundary(
    boundary: BoundaryType | None,
    dim: int,
    *,
    where: str,
    tol: float = 1e-9,
) -> RectChecker | HullChecker:
    """Build the matching checker for a domain ``Boundary`` with ``dim`` axes."""
    shape = None if boundary is None else shape_of(boundary)
    if shape is None:
        raise SimulationError(
            f"domain {where!r} has no ConvexHull or HyperRectangle boundary"
        )
    points = parse_points(shape.point, where=where)
    if not points:
        raise SimulationError(f"domain {where!r}: boundary has no points")
    if len(points[0]) != dim:
        raise SimulationError(
            f"domain {where!r}: boundary points have {len(points[0])} "
            f"coordinate(s) but the domain declares {dim} axes"
        )
    if isinstance(shape, HyperRectangleType):
        return RectChecker(points, where=where, tol=tol)
    return HullChecker(points, where=where, tol=tol)
