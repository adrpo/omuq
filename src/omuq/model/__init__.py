"""Typed data model for omuq documents and the builder functions for it.

The classes in :mod:`omuq.model._generated` are produced by ``xsdata`` from
the omuq schema set (``src/omuq/schemas/uq``) and are the only document
model in omuq-python: builders and the parser return the same classes, so
documents survive attach/save/reopen unchanged. This module adds its helpers
as plain functions; it defines no wrapper classes, subclasses, or
monkey-patched attributes.

The module does three things:

* Re-export the generated classes under stable names, with short aliases
  for the awkward ones (:data:`Study`, :data:`Normal`, :data:`ResultsNormal`).
* Build records with keyword arguments. The builders are the only place
  where xsdata's compound fields (``ActivitiesType.choice``, ``BoundaryType.
  convex_hull_or_hyper_rectangle``, ``SamplingMethodType.pseudo_random_or_
  latin_hyper_cube_or_vendor_specific_sampling``, ...) are written.
* Read documents back through accessors (:func:`activities_of`,
  :func:`shape_of`, :func:`points_of`, ...), so callers do not need the
  compound field names either.

The five activity builders share a keyword core: ``observed=`` (variable
names), ``uncertain=``/``parameters=`` (the parameter set), ``stop=``,
``step=``, ``tolerance=``, ``method=`` (an inline ``SimulationSetting``),
``setting=`` (a prebuilt one instead), ``domain_ref=`` (the activity domain
it runs in), plus ``id=``/``name=``/``description=`` where the schema has
them - ``ForwardUncertaintyQuantification`` has no name or description.

Errors follow the package policy: an unexpected keyword or an object of the
wrong class raises :class:`TypeError`; every other rejection - unknown
enumeration value, ragged point list, conflicting arguments, missing
activity - raises :class:`~omuq.errors.ModelError`.

Regenerating after a schema update::

    xsdata generate src/omuq/schemas/uq/UncertaintyQuantification.xsd \
        --package omuq.model --structure-style single-package \
        --compound-fields --relative-imports

and move the resulting ``model.py`` to ``src/omuq/model/_generated.py``.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping, Sequence

from ..errors import ModelError, SimulationError
from ._generated import (
    ActivitiesType,
    ActivityDomainType,
    ActivitySettingsType,
    AssumptionType,
    AxesType,
    BoundaryType,
    CalibrationType,
    ConvexHullType,
    CoverageClassificationType,
    CredibilityAssessmentType,
    DesiredResultsType,
    DomainCoverageType,
    DomainsType,
    ExperimentPointsType,
    ExternalDocumentType,
    ForwardUncertaintyQuantificationType,
    HyperRectangleType,
    KeyValuesType,
    KeyValueType,
    LatinHypercubeType,
    ModelingAssumptionsType,
    ModelType,
    ObservedVariablesType,
    ObservedVariableType,
    OperationalDomainRefType,
    OperationalDomainType,
    OriginType,
    ParameterSetType,
    ParametersType,
    PercentilesType,
    PointsType,
    ProcessContextType,
    PseudoRandomType,
    RealRangeType,
    RealValueType,
    ReferenceDataType,
    RequiredAssumptionsType,
    ResultSetType,
    ResultsType,
    SamplingMethodType,
    SensitivityAnalysisType,
    SimulationSettingType,
    SobolIndicesType,
    SourceType,
    StringValueType,
    Tparameter,
    Tunit,
    TypedOperationalDomainKind,
    TypedOperationalDomainType,
    UncertainParameterType,
    UncertaintyQuantification,
    UnitsType,
    ValidationType,
    VendorSpecificType,
    VerificationType,
)

# ---------------------------------------------------------------------------
# Aliases, unions, enums
# ---------------------------------------------------------------------------

#: Convenience alias: an omuq document is a "study" in the high level API.
Study = UncertaintyQuantification

#: The five activity types accepted inside an ``Activities`` container.
ACTIVITY_TYPES = (
    VerificationType,
    CalibrationType,
    ValidationType,
    SensitivityAnalysisType,
    ForwardUncertaintyQuantificationType,
)

#: Union of the five activity classes (see :data:`ACTIVITY_TYPES`).
Activity = (
    VerificationType
    | CalibrationType
    | ValidationType
    | SensitivityAnalysisType
    | ForwardUncertaintyQuantificationType
)

# Distribution element classes (inner classes of the generated
# UncertainParameterType, one per GDistribution choice element).
Normal = UncertainParameterType.Normal
NormalTolerance = UncertainParameterType.NormalTolerance
Uniform = UncertainParameterType.Uniform
UniformTolerance = UncertainParameterType.UniformTolerance
Weibull = UncertainParameterType.Weibull
Cauchy = UncertainParameterType.Cauchy
CauchyTolerance = UncertainParameterType.CauchyTolerance
MonotoneSplineCDF = UncertainParameterType.MonotoneSplineCdf

DISTRIBUTIONS = (
    Normal,
    NormalTolerance,
    Uniform,
    UniformTolerance,
    Weibull,
    Cauchy,
    CauchyTolerance,
    MonotoneSplineCDF,
)

#: A parameter distribution: one of :data:`DISTRIBUTIONS` or a vendor one.
Distribution = (
    Normal
    | NormalTolerance
    | Uniform
    | UniformTolerance
    | Weibull
    | Cauchy
    | CauchyTolerance
    | MonotoneSplineCDF
    | VendorSpecificType
)

# Result distributions are different classes from parameter distributions:
# the schema reuses the GDistribution group inside Results, so xsdata emits a
# second set of inner classes. Mixing them up is a validation error.
ResultsNormal = ResultsType.Normal
ResultsNormalTolerance = ResultsType.NormalTolerance
ResultsUniform = ResultsType.Uniform
ResultsUniformTolerance = ResultsType.UniformTolerance
ResultsWeibull = ResultsType.Weibull
ResultsCauchy = ResultsType.Cauchy
ResultsCauchyTolerance = ResultsType.CauchyTolerance
ResultsMonotoneSplineCDF = ResultsType.MonotoneSplineCdf

RESULT_DISTRIBUTIONS = (
    ResultsNormal,
    ResultsNormalTolerance,
    ResultsUniform,
    ResultsUniformTolerance,
    ResultsWeibull,
    ResultsCauchy,
    ResultsCauchyTolerance,
    ResultsMonotoneSplineCDF,
)

#: One error metric inside a ``Results`` element (RMSE, MAE, ...).
ErrorMetric = ResultsType.ErrorMetric

#: Anything that may appear inside a ``Results`` element.
ResultItem = (
    ResultsNormal
    | ResultsNormalTolerance
    | ResultsUniform
    | ResultsUniformTolerance
    | ResultsWeibull
    | ResultsCauchy
    | ResultsCauchyTolerance
    | ResultsMonotoneSplineCDF
    | VendorSpecificType
    | ErrorMetric
)

#: One reference data source inside a ``ReferenceData`` element.
DataSource = ReferenceDataType.DataSource

#: One calibration target inside a ``Calibration`` activity.
CalibrationTarget = CalibrationType.CalibrationTargets.Target

#: One region inside a ``DomainCoverage`` element.
Region = DomainCoverageType.Region

#: A boundary shape.
Shape = ConvexHullType | HyperRectangleType

#: A domain with axes and a boundary (coverage records are not domains).
Domain = TypedOperationalDomainType | ActivityDomainType


class Sampling(str, enum.Enum):
    """The sampling methods omuq-python can build.

    Named ``Sampling`` rather than ``SamplingMethod`` because the generated
    model already uses that name for the container element. Vendor sampling
    is expressed with a ``VendorSpecificType`` assigned to the activity's
    ``sampling_method`` and has no member here.
    """

    PSEUDO_RANDOM = "PseudoRandom"
    LATIN_HYPERCUBE = "LatinHyperCube"


_SAMPLING_CLASSES = {
    Sampling.PSEUDO_RANDOM: PseudoRandomType,
    Sampling.LATIN_HYPERCUBE: LatinHypercubeType,
}


# ---------------------------------------------------------------------------
# Small coercions shared by the builders
# ---------------------------------------------------------------------------


def _float(value: float | None) -> float | None:
    """Coerce to float so that ints survive a serialize/parse round trip."""
    return None if value is None else float(value)


def _enum(cls, value, *, what: str):
    """Coerce ``value`` into the enum ``cls`` or raise :class:`ModelError`."""
    try:
        return cls(value)
    except ValueError:
        allowed = ", ".join(repr(m.value) for m in cls)
        raise ModelError(
            f"unknown {what} {value!r}; expected one of {allowed}"
        ) from None


def _point_rows(
    points: Iterable[Sequence[float]], *, where: str
) -> list[tuple[float, ...]]:
    """Validate a point cloud: non-empty, numeric, all of the same dimension."""
    rows: list[tuple[float, ...]] = []
    for index, point in enumerate(points):
        if isinstance(point, str):
            raise TypeError(
                f"{where}: point {index + 1} must be a sequence of numbers, "
                f"got the string {point!r}"
            )
        try:
            row = tuple(float(c) for c in point)
        except (TypeError, ValueError) as exc:
            raise ModelError(
                f"{where}: point {index + 1} is not a sequence of numbers: {point!r}"
            ) from exc
        if not row:
            raise ModelError(f"{where}: point {index + 1} has no coordinates")
        if rows and len(row) != len(rows[0]):
            raise ModelError(
                f"{where}: point {index + 1} has {len(row)} coordinate(s), "
                f"expected {len(rows[0])}"
            )
        rows.append(row)
    if not rows:
        raise ModelError(f"{where}: at least one point is required")
    return rows


def _coordinates(row: Sequence[float]) -> str:
    """The ``coordinates`` attribute of a Point: ``repr`` keeps every digit."""
    return " ".join(repr(c) for c in row)


def _as_axes(value: AxesType | Sequence[str]) -> AxesType:
    if isinstance(value, AxesType):
        return value
    if isinstance(value, str):
        raise TypeError(
            "axes must be an AxesType or a sequence of axis names, not the "
            f"single string {value!r}"
        )
    return axes(*value)


def _as_boundary(value: Shape | BoundaryType) -> BoundaryType:
    return value if isinstance(value, BoundaryType) else boundary(value)


def _as_domains(value: DomainsType | Iterable) -> DomainsType:
    return value if isinstance(value, DomainsType) else domains(*value)


# ---------------------------------------------------------------------------
# Geometry and domain builders
# ---------------------------------------------------------------------------


def axes(*names: str, units: Mapping[str, str] | None = None) -> AxesType:
    """Build an ``Axes`` element from axis names in coordinate order.

    ``units`` optionally maps an axis name to its unit. Naming an axis that
    was not declared is an error.
    """
    if not names:
        raise ModelError(
            "axes() needs at least one axis name; the axis order defines the "
            "coordinate order of every Point in the domain's boundary"
        )
    units = dict(units or {})
    unknown = sorted(set(units) - set(names))
    if unknown:
        raise ModelError(
            f"axes(): units name unknown axes {', '.join(repr(u) for u in unknown)}; "
            f"declared axes are {', '.join(repr(n) for n in names)}"
        )
    return AxesType(axis=[AxesType.Axis(name=n, unit=units.get(n)) for n in names])


def convex_hull(points: Iterable[Sequence[float]]) -> ConvexHullType:
    """Build a ``ConvexHull`` boundary shape from its vertices.

    Coordinates are written with ``repr`` so that parsing the document back
    yields exactly the floats that went in.
    """
    rows = _point_rows(points, where="convex_hull()")
    return ConvexHullType(
        point=[ConvexHullType.Point(coordinates=_coordinates(r)) for r in rows]
    )


def hyper_rectangle(lo: Sequence[float], hi: Sequence[float]) -> HyperRectangleType:
    """Build a ``HyperRectangle`` boundary shape from its two corner points."""
    rows = _point_rows([lo, hi], where="hyper_rectangle()")
    low, high = rows
    for index, (a, b) in enumerate(zip(low, high, strict=True)):
        if a > b:
            raise ModelError(
                f"hyper_rectangle(): lo[{index}]={a!r} is greater than "
                f"hi[{index}]={b!r}; pass the lower corner first"
            )
    return HyperRectangleType(
        point=[HyperRectangleType.Point(coordinates=_coordinates(r)) for r in rows]
    )


def boundary(shape: Shape) -> BoundaryType:
    """Wrap a :data:`Shape` in a ``Boundary`` element."""
    if not isinstance(shape, (ConvexHullType, HyperRectangleType)):
        raise TypeError(
            f"boundary() needs a ConvexHull or a HyperRectangle, got "
            f"{type(shape).__name__}; build one with convex_hull() or "
            "hyper_rectangle()"
        )
    return BoundaryType(convex_hull_or_hyper_rectangle=shape)


def _geometry_kind(bound: BoundaryType) -> str | None:
    shape = bound.convex_hull_or_hyper_rectangle
    if isinstance(shape, HyperRectangleType):
        return "HyperRectangle"
    if isinstance(shape, ConvexHullType):
        return "ConvexHull"
    return None


def operational_domain(
    id: str,
    axes: AxesType | Sequence[str],
    boundary: Shape | BoundaryType,
    *,
    kind: TypedOperationalDomainKind
    | str = TypedOperationalDomainKind.MODELED_OPERATIONAL_DOMAIN,
    name: str | None = None,
    description: str | None = None,
    parent_ref: str | None = None,
) -> TypedOperationalDomainType:
    """Build a ``TypedOperationalDomain`` (ODD, requested OD, or modeled OD).

    ``axes`` accepts an ``AxesType`` or a sequence of axis names, ``boundary``
    a shape or a prebuilt ``Boundary``; ``geometryKind`` is derived from the
    shape. ``kind`` accepts the enum or its string value.
    """
    bound = _as_boundary(boundary)
    return TypedOperationalDomainType(
        axes=_as_axes(axes),
        boundary=bound,
        description=description,
        id=id,
        name=name,
        kind=_enum(TypedOperationalDomainKind, kind, what="operational domain kind"),
        geometry_kind=_geometry_kind(bound),
        parent_ref=parent_ref,
    )


def activity_domain(
    id: str,
    axes: AxesType | Sequence[str],
    boundary: Shape | BoundaryType,
    *,
    kind: str = "Validation",
    name: str | None = None,
    domain_ref: str | None = None,
    description: str | None = None,
) -> ActivityDomainType:
    """Build an ``ActivityDomain`` - the domain one activity is scoped to.

    ``kind`` is a plain string in the schema; the recommended values are
    ``Verification``, ``Calibration``, ``Validation``,
    ``UncertaintyQuantification`` and ``SensitivityAnalysis``.
    ``domain_ref`` points at the parent (typically the modeled OD).
    """
    return ActivityDomainType(
        axes=_as_axes(axes),
        boundary=_as_boundary(boundary),
        description=description,
        id=id,
        name=name,
        kind=kind,
        domain_ref=domain_ref,
    )


def domains(*items: Domain | DomainCoverageType) -> DomainsType:
    """Build a ``Domains`` container, sorting the items into their slots."""
    typed: list[TypedOperationalDomainType] = []
    activity: list[ActivityDomainType] = []
    coverage: list[DomainCoverageType] = []
    for item in items:
        if isinstance(item, TypedOperationalDomainType):
            typed.append(item)
        elif isinstance(item, ActivityDomainType):
            activity.append(item)
        elif isinstance(item, DomainCoverageType):
            coverage.append(item)
        else:
            raise TypeError(
                f"{type(item).__name__} is neither a domain nor a domain "
                "coverage; build one with operational_domain(), "
                "activity_domain() or domain_coverage()"
            )
    return DomainsType(
        typed_operational_domain=typed,
        activity_domain=activity,
        domain_coverage=coverage,
    )


def domain_coverage(
    requested: str,
    realized: str,
    *,
    regions: Iterable[Region | Sequence],
    id: str | None = None,
    description: str | None = None,
) -> DomainCoverageType:
    """Build a ``DomainCoverage`` element comparing two domains by region.

    ``requested``/``realized`` are the ids of the two domains being compared.
    Each region is a :data:`Region` or a ``(classification, boundary,
    description)`` tuple whose last two members may be omitted;
    ``classification`` accepts a :class:`CoverageClassificationType` or its
    string value.
    """
    built: list[Region] = []
    for item in regions:
        if isinstance(item, Region):
            built.append(item)
            continue
        classification, *rest = item
        bound, text = (list(rest) + [None, None])[:2]
        built.append(
            Region(
                boundary=None if bound is None else _as_boundary(bound),
                description=text,
                classification=_enum(
                    CoverageClassificationType,
                    classification,
                    what="coverage classification",
                ),
            )
        )
    return DomainCoverageType(
        region=built,
        description=description,
        id=id,
        requested_domain_ref=requested,
        realized_domain_ref=realized,
    )


# ---------------------------------------------------------------------------
# Parameter and activity builders
# ---------------------------------------------------------------------------


def uncertain_parameter(
    name: str,
    distribution: Distribution,
    *,
    source: SourceType | str | None = None,
    description: str | None = None,
    id: str | None = None,
    source_info: str | None = None,
) -> UncertainParameterType:
    """Build an ``UncertainParameter`` record around a distribution instance.

    ``distribution`` must be an instance of one of the classes listed in
    :data:`DISTRIBUTIONS` (for example ``Normal(mu=0.05, sigma=0.005)``) or a
    ``VendorSpecificType``.
    """
    if isinstance(source, str):
        source = _enum(SourceType, source, what="parameter source")
    if not isinstance(distribution, DISTRIBUTIONS + (VendorSpecificType,)):
        raise TypeError(
            f"unsupported distribution object {type(distribution).__name__}; "
            "use one of omuq.model.DISTRIBUTIONS or VendorSpecificType"
        )
    return UncertainParameterType(
        name=name,
        choice=distribution,
        source=source,
        description=description,
        id=id,
        source_info=source_info,
    )


def simulation_setting(
    *,
    stop_time: float | None = None,
    interval: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    description: str | None = None,
) -> SimulationSettingType:
    """Build a ``SimulationSetting`` record for an activity.

    ``interval`` is the communication step size and ``stop_time`` the end of
    the simulated time span. The activity builders take these as ``step=``
    and ``stop=``; use this function only for a setting you want to share
    between activities or fill in further.
    """
    return SimulationSettingType(
        stop_time=_float(stop_time),
        interval=_float(interval),
        tolerance=_float(tolerance),
        method=method,
        description=description,
    )


def _parameter_set(
    uncertain: Sequence[UncertainParameterType] | None,
    parameters: Sequence[Tparameter] | None,
) -> ParameterSetType | None:
    if not uncertain and not parameters:
        return None
    return ParameterSetType(
        parameters=ParametersType(
            parameter=list(parameters or []),
            uncertain_parameter=list(uncertain or []),
        )
    )


def _observed_variables(observed: Sequence[str] | None) -> ObservedVariablesType | None:
    if not observed:
        return None
    return ObservedVariablesType(
        observed_variable=[ObservedVariableType(name=n) for n in observed]
    )


def _sampling_method(
    samples: int | None, sampling: Sampling | str
) -> SamplingMethodType | None:
    # Validate sampling= before the samples check, so an invalid value is
    # rejected even when samples is None.
    method = _SAMPLING_CLASSES[_enum(Sampling, sampling, what="sampling method")]
    if samples is None:
        return None
    return SamplingMethodType(
        pseudo_random_or_latin_hyper_cube_or_vendor_specific_sampling=method(
            number_of_samples=samples
        )
    )


def _setting(
    setting: SimulationSettingType | None,
    stop: float | None,
    step: float | None,
    tolerance: float | None,
    method: str | None,
) -> SimulationSettingType | None:
    inline = {"stop": stop, "step": step, "tolerance": tolerance, "method": method}
    given = [k for k, v in inline.items() if v is not None]
    if setting is not None:
        if given:
            raise ModelError(
                "pass either a prebuilt setting= or the inline simulation "
                f"settings ({', '.join(given)}), not both"
            )
        return setting
    if not given:
        return None
    return simulation_setting(
        stop_time=stop, interval=step, tolerance=tolerance, method=method
    )


def _activity_core(
    *,
    observed: Sequence[str] | None,
    uncertain: Sequence[UncertainParameterType] | None,
    parameters: Sequence[Tparameter] | None,
    stop: float | None,
    step: float | None,
    tolerance: float | None,
    method: str | None,
    setting: SimulationSettingType | None,
    domain_ref: str | None,
    id: str | None,
) -> dict:
    """The fields every activity type shares, as constructor keywords."""
    return {
        "parameter_set": _parameter_set(uncertain, parameters),
        "observed_variables": _observed_variables(observed),
        "simulation_setting": _setting(setting, stop, step, tolerance, method),
        "activity_domain_ref": domain_ref,
        "id": id,
    }


def _reject_forward_uq_kwargs(kwargs: dict) -> None:
    named = [k for k in ("name", "description") if k in kwargs]
    if named:
        raise TypeError(
            "ForwardUncertaintyQuantification has no "
            + " or ".join(named)
            + " attribute in the omuq schema (UncertaintyQuantification.xsd, "
            "ForwardUncertaintyQuantificationType); identify the activity "
            "with id=, or use another activity builder"
        )
    unexpected = next(iter(kwargs))
    raise TypeError(f"forward_uq() got an unexpected keyword argument {unexpected!r}")


def forward_uq(
    *,
    uncertain: Sequence[UncertainParameterType] | None = None,
    parameters: Sequence[Tparameter] | None = None,
    observed: Sequence[str] | None = None,
    samples: int | None = None,
    sampling: Sampling | str = Sampling.LATIN_HYPERCUBE,
    desired: DesiredResultsType | None = None,
    stop: float | None = None,
    step: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    setting: SimulationSettingType | None = None,
    domain_ref: str | None = None,
    id: str | None = None,
    **unsupported,
) -> ForwardUncertaintyQuantificationType:
    """Build a ``ForwardUncertaintyQuantification`` activity.

    ``observed`` lists the variable names to record and ``samples`` the size
    of the sample set drawn with ``sampling``. This activity type has no
    name or description in the schema; passing either raises
    :class:`TypeError`.
    """
    if unsupported:
        _reject_forward_uq_kwargs(unsupported)
    return ForwardUncertaintyQuantificationType(
        **_activity_core(
            observed=observed,
            uncertain=uncertain,
            parameters=parameters,
            stop=stop,
            step=step,
            tolerance=tolerance,
            method=method,
            setting=setting,
            domain_ref=domain_ref,
            id=id,
        ),
        desired_results=desired,
        sampling_method=_sampling_method(samples, sampling),
    )


def validation(
    *,
    uncertain: Sequence[UncertainParameterType] | None = None,
    parameters: Sequence[Tparameter] | None = None,
    observed: Sequence[str] | None = None,
    samples: int | None = None,
    sampling: Sampling | str = Sampling.LATIN_HYPERCUBE,
    desired: DesiredResultsType | None = None,
    reference: ReferenceDataType | None = None,
    stop: float | None = None,
    step: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    setting: SimulationSettingType | None = None,
    domain_ref: str | None = None,
    id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> ValidationType:
    """Build a ``Validation`` activity (model vs. reference measurements)."""
    return ValidationType(
        **_activity_core(
            observed=observed,
            uncertain=uncertain,
            parameters=parameters,
            stop=stop,
            step=step,
            tolerance=tolerance,
            method=method,
            setting=setting,
            domain_ref=domain_ref,
            id=id,
        ),
        desired_results=desired,
        sampling_method=_sampling_method(samples, sampling),
        reference_data=reference,
        name=name,
        description=description,
    )


def verification(
    *,
    uncertain: Sequence[UncertainParameterType] | None = None,
    parameters: Sequence[Tparameter] | None = None,
    observed: Sequence[str] | None = None,
    samples: int | None = None,
    sampling: Sampling | str = Sampling.LATIN_HYPERCUBE,
    desired: DesiredResultsType | None = None,
    reference: ReferenceDataType | None = None,
    stop: float | None = None,
    step: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    setting: SimulationSettingType | None = None,
    domain_ref: str | None = None,
    id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> VerificationType:
    """Build a ``Verification`` activity (model vs. an analytical answer)."""
    return VerificationType(
        **_activity_core(
            observed=observed,
            uncertain=uncertain,
            parameters=parameters,
            stop=stop,
            step=step,
            tolerance=tolerance,
            method=method,
            setting=setting,
            domain_ref=domain_ref,
            id=id,
        ),
        desired_results=desired,
        sampling_method=_sampling_method(samples, sampling),
        reference_data=reference,
        name=name,
        description=description,
    )


def sensitivity_analysis(
    *,
    uncertain: Sequence[UncertainParameterType] | None = None,
    parameters: Sequence[Tparameter] | None = None,
    observed: Sequence[str] | None = None,
    samples: int | None = None,
    sampling: Sampling | str = Sampling.LATIN_HYPERCUBE,
    desired: DesiredResultsType | None = None,
    stop: float | None = None,
    step: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    setting: SimulationSettingType | None = None,
    domain_ref: str | None = None,
    id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> SensitivityAnalysisType:
    """Build a ``SensitivityAnalysis`` activity (Sobol indices and friends)."""
    return SensitivityAnalysisType(
        **_activity_core(
            observed=observed,
            uncertain=uncertain,
            parameters=parameters,
            stop=stop,
            step=step,
            tolerance=tolerance,
            method=method,
            setting=setting,
            domain_ref=domain_ref,
            id=id,
        ),
        desired_results=desired,
        sampling_method=_sampling_method(samples, sampling),
        name=name,
        description=description,
    )


def calibration_target(
    parameter_name: str,
    *,
    initial: float | None = None,
    lower: float | None = None,
    upper: float | None = None,
    unit: str | None = None,
) -> CalibrationTarget:
    """Build one calibration ``Target``: the parameter and its search range."""
    return CalibrationTarget(
        parameter_name=parameter_name,
        initial_value=_float(initial),
        lower_bound=_float(lower),
        upper_bound=_float(upper),
        unit=unit,
    )


def calibration(
    *,
    targets: Iterable[CalibrationTarget],
    reference: ReferenceDataType | None = None,
    uncertain: Sequence[UncertainParameterType] | None = None,
    parameters: Sequence[Tparameter] | None = None,
    observed: Sequence[str] | None = None,
    stop: float | None = None,
    step: float | None = None,
    tolerance: float | None = None,
    method: str | None = None,
    setting: SimulationSettingType | None = None,
    domain_ref: str | None = None,
    id: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> CalibrationType:
    """Build a ``Calibration`` activity.

    Calibration has no sampling method and no desired results in the schema;
    it has calibration targets and reference data instead.
    """
    built = list(targets)
    if not built:
        raise ModelError(
            "calibration() needs at least one target; build them with "
            "calibration_target(parameter_name, ...)"
        )
    return CalibrationType(
        **_activity_core(
            observed=observed,
            uncertain=uncertain,
            parameters=parameters,
            stop=stop,
            step=step,
            tolerance=tolerance,
            method=method,
            setting=setting,
            domain_ref=domain_ref,
            id=id,
        ),
        reference_data=reference,
        calibration_targets=CalibrationType.CalibrationTargets(target=built),
        name=name,
        description=description,
    )


# ---------------------------------------------------------------------------
# Result, reference and assumption builders
# ---------------------------------------------------------------------------


def desired_results(
    *,
    mean: bool | None = None,
    std: bool | None = None,
    percentiles: Sequence[float] | None = None,
    sobol_order: int | None = None,
    sobol_total: bool | None = None,
    histogram: bool | None = None,
    pdf: bool | None = None,
    cdf: bool | None = None,
    quantile: bool | None = None,
    data: str | None = None,
    summary: str | None = None,
    scope: str | None = None,
    description: str | None = None,
) -> DesiredResultsType:
    """Build a ``DesiredResults`` element: what the run should produce.

    ``std`` is the schema's ``standardDeviation``; ``percentiles`` are the
    requested levels in percent; ``sobol_order``/``sobol_total`` fill the
    ``SobolIndices`` child, whose ``order`` the schema requires.
    """
    if sobol_order is None and sobol_total is not None:
        raise ModelError(
            f"desired_results(): sobol_total={sobol_total!r} needs "
            "sobol_order= as well; the schema's SobolIndices element requires "
            "an order, so there is nowhere to record the total on its own"
        )
    return DesiredResultsType(
        percentiles=(
            None
            if percentiles is None
            else PercentilesType(level=[float(p) for p in percentiles])
        ),
        sobol_indices=(
            None
            if sobol_order is None
            else SobolIndicesType(order=int(sobol_order), total=sobol_total)
        ),
        data=data,
        summary=summary,
        scope=scope,
        mean=mean,
        standard_deviation=std,
        histogram=histogram,
        pdf=pdf,
        cdf=cdf,
        quantile=quantile,
        description=description,
    )


def reference_data(
    sources: Iterable[DataSource | str | Sequence[str]],
    *,
    description: str | None = None,
) -> ReferenceDataType:
    """Build a ``ReferenceData`` element from its data sources.

    Each source is a :data:`DataSource`, a plain name, or a ``(name, file,
    type, description)`` tuple whose trailing members may be omitted.
    """
    built: list[DataSource] = []
    for item in sources:
        if isinstance(item, DataSource):
            built.append(item)
        elif isinstance(item, str):
            built.append(DataSource(name=item))
        else:
            name, *rest = item
            file, type_value, text = (list(rest) + [None, None, None])[:3]
            built.append(
                DataSource(
                    name=name, file=file, type_value=type_value, description=text
                )
            )
    return ReferenceDataType(data_source=built, description=description)


def error_metric(
    type: str,
    value: float,
    *,
    name: str | None = None,
    threshold: float | None = None,
    passed: bool | None = None,
    observed_variable: str | None = None,
) -> ErrorMetric:
    """Build one ``ErrorMetric`` result (``passed`` is the schema's ``pass``)."""
    return ErrorMetric(
        name=name,
        type_value=type,
        value=float(value),
        threshold=_float(threshold),
        pass_value=passed,
        observed_variable=observed_variable,
    )


def results(*items: ResultItem, point: str | None = None) -> ResultsType:
    """Build one ``Results`` element from result distributions and metrics.

    The distributions here are the :data:`RESULT_DISTRIBUTIONS` classes
    (``ResultsNormal`` and friends), not the parameter ones.
    """
    for item in items:
        if not isinstance(item, ResultItem):
            raise TypeError(
                f"{type(item).__name__} is not a result item; use one of "
                "omuq.model.RESULT_DISTRIBUTIONS, VendorSpecificType, or "
                "error_metric()"
            )
    return ResultsType(choice=list(items), point=point)


def result_set(*items: ResultsType) -> ResultSetType:
    """Build a ``ResultSet`` from one or more ``Results`` elements."""
    return ResultSetType(results=list(items))


def assumption(
    name: str,
    value: float | str | Sequence[float] | object | None = None,
    *,
    unit: str | None = None,
    id: str | None = None,
    description: str | None = None,
    origin: OriginType | str | None = None,
    domain_refs: Sequence[str] | None = None,
) -> AssumptionType:
    """Build an ``Assumption`` with its value coerced to the right element.

    A number becomes ``Real``, a ``(low, high)`` pair ``RealRange``, a string
    ``Text``, and ``None`` an assumption without a value. Pass a
    ``StringValueType`` or ``ExternalDocumentType`` for the remaining two
    choices. ``unit`` applies to the numeric forms only - a prebuilt value
    object carries its own, so combining the two is rejected.
    """
    prebuilt = (RealValueType, RealRangeType, StringValueType, ExternalDocumentType)
    # Track whether unit= was consumed during coercion; a prebuilt
    # RealValueType cannot be told apart from a coerced one afterwards.
    unit_used = False
    if value is None or isinstance(value, prebuilt):
        choice = value
    elif isinstance(value, str):
        choice = value
    elif isinstance(value, (int, float)):
        choice = RealValueType(value=float(value), unit=unit)
        unit_used = True
    elif isinstance(value, Sequence) and len(value) == 2:
        choice = RealRangeType(low=float(value[0]), high=float(value[1]), unit=unit)
        unit_used = True
    else:
        raise TypeError(
            f"cannot express {type(value).__name__} as an assumption value; "
            "use a number, a (low, high) pair, a string, or a RealValueType/"
            "RealRangeType/StringValueType/ExternalDocumentType"
        )
    if unit is not None and not unit_used:
        raise ModelError(
            f"assumption {name!r}: unit={unit!r} applies to a number or a "
            "(low, high) pair; a prebuilt value object carries its own unit "
            "attribute, and a text or empty assumption has nowhere to put one"
        )
    return AssumptionType(
        operational_domain_ref=[
            OperationalDomainRefType(ref=r) for r in (domain_refs or [])
        ],
        choice=choice,
        id=id,
        name=name,
        description=description,
        origin=(
            None
            if origin is None
            else _enum(OriginType, origin, what="assumption origin")
        ),
    )


def _assumption_list(
    assumptions: Iterable[AssumptionType], *, where: str
) -> list[AssumptionType]:
    built = list(assumptions)
    if not built:
        raise ModelError(f"{where} needs at least one assumption")
    return built


def required_assumptions(
    id: str,
    assumptions: Iterable[AssumptionType],
    *,
    description: str | None = None,
) -> RequiredAssumptionsType:
    """Build a ``RequiredAssumptions`` block (assumptions the model must make)."""
    return RequiredAssumptionsType(
        assumption=_assumption_list(assumptions, where="required_assumptions()"),
        id=id,
        description=description,
    )


def modeling_assumptions(
    id: str,
    assumptions: Iterable[AssumptionType],
    *,
    description: str | None = None,
) -> ModelingAssumptionsType:
    """Build a ``ModelingAssumptions`` block (assumptions the model makes)."""
    return ModelingAssumptionsType(
        assumption=_assumption_list(assumptions, where="modeling_assumptions()"),
        id=id,
        description=description,
    )


def model_info(
    *,
    name: str | None = None,
    file: str | None = None,
    model: str | None = None,
    resource_meta_data: str | None = None,
    assumptions: ModelingAssumptionsType
    | Iterable[ModelingAssumptionsType]
    | None = None,
) -> ModelType:
    """Build the study's ``Model`` element (what was simulated)."""
    if assumptions is None:
        blocks: list[ModelingAssumptionsType] = []
    elif isinstance(assumptions, ModelingAssumptionsType):
        blocks = [assumptions]
    else:
        blocks = list(assumptions)
    return ModelType(
        modeling_assumptions=blocks,
        name=name,
        file=file,
        model=model,
        model_resource_meta_data=resource_meta_data,
    )


def credibility_assessment(
    level: str,
    *,
    purpose: str | None = None,
    standard: str | None = None,
    description: str | None = None,
) -> CredibilityAssessmentType:
    """Build a ``CredibilityAssessment`` for a typed operational domain."""
    return CredibilityAssessmentType(
        description=description,
        level=level,
        purpose=purpose,
        standard=standard,
    )


def process_context(
    *,
    process: str | None = None,
    phase: str | None = None,
    glue_particle_ref: str | None = None,
    description: str | None = None,
) -> ProcessContextType:
    """Build a ``ProcessContext`` (which process/phase an artifact belongs to)."""
    return ProcessContextType(
        description=description,
        process=process,
        phase=phase,
        glue_particle_ref=glue_particle_ref,
    )


def study(
    name: str,
    *,
    activities: Iterable[Activity] | None = None,
    domains: DomainsType | Iterable[Domain | DomainCoverageType] | None = None,
    info: str | None = None,
    author: str | None = None,
) -> UncertaintyQuantification:
    """Build a study (an ``UncertaintyQuantification`` document root).

    ``activities`` and ``domains`` each accept any iterable, including a
    generator: both are materialized with ``list(...)`` before validation,
    so the iterable is consumed only once. ``domains`` also accepts a
    prebuilt ``DomainsType`` (see :func:`domains`).
    """
    acts = None
    if activities is not None:
        activities = list(activities)
        for a in activities:
            if not isinstance(a, ACTIVITY_TYPES):
                raise TypeError(
                    f"{type(a).__name__} is not a valid activity; "
                    "expected one of omuq.model.ACTIVITY_TYPES"
                )
        if activities:
            acts = ActivitiesType(choice=activities)
    doms = None
    # An empty iterable produces no Domains element; a prebuilt DomainsType
    # is used as given, even when empty.
    if isinstance(domains, DomainsType):
        doms = _as_domains(domains)
    elif domains is not None:
        domains = list(domains)
        if domains:
            doms = _as_domains(domains)
    return UncertaintyQuantification(
        domains=doms,
        activities=acts,
        name=name,
        author=author,
        info=info,
    )


# ---------------------------------------------------------------------------
# Accessors: read a document without naming a compound field
# ---------------------------------------------------------------------------


def activities_of(study: UncertaintyQuantification) -> list[Activity]:
    """Every activity of a study, in document order."""
    return list(study.activities.choice) if study.activities is not None else []


def activity_of(study: UncertaintyQuantification, key: int | str = 0) -> Activity:
    """One activity by position, or by ``id`` and then by ``name``.

    Raises :class:`~omuq.errors.ModelError` when the study has no such
    activity.
    """
    acts = activities_of(study)
    if not acts:
        raise ModelError(f"study {study.name!r} has no activities")
    if isinstance(key, str):
        for act in acts:
            if act.id == key:
                return act
        for act in acts:
            if getattr(act, "name", None) == key:
                return act
        known = ", ".join(repr(a.id) for a in acts if a.id) or "none with an id"
        raise ModelError(
            f"study {study.name!r} has no activity with id or name {key!r} "
            f"(known ids: {known})"
        )
    try:
        return acts[key]
    except IndexError:
        raise ModelError(
            f"study {study.name!r} has no activity at index {key}; it has {len(acts)}"
        ) from None


def add_activity(study: UncertaintyQuantification, activity: Activity) -> Activity:
    """Append an activity, creating the ``Activities`` container on demand."""
    if not isinstance(activity, ACTIVITY_TYPES):
        raise TypeError(
            f"{type(activity).__name__} is not a valid activity; "
            "expected one of omuq.model.ACTIVITY_TYPES"
        )
    if study.activities is None:
        study.activities = ActivitiesType()
    study.activities.choice.append(activity)
    return activity


def _domains_container(study: UncertaintyQuantification) -> DomainsType:
    if study.domains is None:
        study.domains = DomainsType()
    return study.domains


def domains_of(study: UncertaintyQuantification) -> list[Domain]:
    """Every typed operational domain and activity domain of a study."""
    container = study.domains
    if container is None:
        return []
    return [*container.typed_operational_domain, *container.activity_domain]


def find_domain(study: UncertaintyQuantification, id: str) -> Domain | None:
    """The domain with this id, or ``None``."""
    for domain in domains_of(study):
        if domain.id == id:
            return domain
    return None


def add_domain(
    study: UncertaintyQuantification, domain: Domain | DomainCoverageType
) -> Domain | DomainCoverageType:
    """Append a domain (or a coverage), creating ``Domains`` on demand."""
    container = _domains_container(study)
    if isinstance(domain, TypedOperationalDomainType):
        container.typed_operational_domain.append(domain)
    elif isinstance(domain, ActivityDomainType):
        container.activity_domain.append(domain)
    elif isinstance(domain, DomainCoverageType):
        container.domain_coverage.append(domain)
    else:
        raise TypeError(
            f"{type(domain).__name__} is neither a domain nor a domain "
            "coverage; build one with operational_domain(), "
            "activity_domain() or domain_coverage()"
        )
    return domain


def upsert_coverage(
    study: UncertaintyQuantification, coverage: DomainCoverageType
) -> DomainCoverageType:
    """Add a domain coverage, replacing an existing one with the same id."""
    container = _domains_container(study)
    if coverage.id is not None:
        for index, existing in enumerate(container.domain_coverage):
            if existing.id == coverage.id:
                container.domain_coverage[index] = coverage
                return coverage
    container.domain_coverage.append(coverage)
    return coverage


def shape_of(obj) -> Shape | None:
    """The ``ConvexHull``/``HyperRectangle`` of a shape, boundary or domain."""
    if isinstance(obj, (ConvexHullType, HyperRectangleType)):
        return obj
    if isinstance(obj, BoundaryType):
        return obj.convex_hull_or_hyper_rectangle
    bound = getattr(obj, "boundary", None)
    return None if bound is None else bound.convex_hull_or_hyper_rectangle


def points_of(obj) -> list[tuple[float, ...]]:
    """The boundary points of a shape, boundary or domain, as float tuples.

    Returns an empty list when there is no boundary to read.
    """
    # Local import: omuq.geometry imports this module for its own types.
    from ..geometry import parse_points

    shape = shape_of(obj)
    if shape is None:
        return []
    return parse_points(
        shape.point, where=getattr(obj, "id", None) or type(obj).__name__
    )


def axis_names(domain: Domain | AxesType | None) -> tuple[str, ...]:
    """The axis names of a domain (or of an ``Axes`` element), in order."""
    ax = domain if isinstance(domain, AxesType) else getattr(domain, "axes", None)
    return () if ax is None else tuple(a.name for a in ax.axis)


def observed_names(activity: Activity) -> tuple[str, ...]:
    """The activity's inline observed-variable names, in document order."""
    ov = getattr(activity, "observed_variables", None)
    if ov is not None and ov.source is not None and not ov.observed_variable:
        raise SimulationError(
            f"the activity's observed variables are externalized to "
            f"{ov.source!r}; inline ObservedVariable elements are required "
            "to run a simulation"
        )
    if ov is None or not ov.observed_variable:
        raise SimulationError(
            "the activity declares no ObservedVariables; the study must "
            "list the variables to record"
        )
    names = tuple(v.name for v in ov.observed_variable)
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise SimulationError(f"duplicate observed variable {name!r}")
        seen.add(name)
    return names


def results_of(activity: Activity) -> list[ResultsType]:
    """Every ``Results`` element of an activity's ``ResultSet``, in order.

    Returns an empty list when the activity has no ``ResultSet``; one is
    written by :meth:`omuq.package.UqManager.record_result`.
    """
    result_set = getattr(activity, "result_set", None)
    return [] if result_set is None else list(result_set.results)


def result_items(results: ResultsType) -> list[ResultItem]:
    """Everything inside one ``Results`` element, in document order.

    Error metrics, result distributions and vendor entries are returned
    interleaved in the order they were written; filter by class, for
    example ``isinstance(item, ErrorMetric)``.
    """
    return list(results.choice)


def distribution_of(param: UncertainParameterType) -> Distribution | None:
    """The distribution of an uncertain parameter, or ``None``."""
    return param.choice


def sampling_of(
    activity: Activity,
) -> PseudoRandomType | LatinHypercubeType | VendorSpecificType | None:
    """The sampling method of an activity, or ``None``.

    ``Calibration`` has no sampling method in the schema and always yields
    ``None``.
    """
    method = getattr(activity, "sampling_method", None)
    if method is None:
        return None
    return method.pseudo_random_or_latin_hyper_cube_or_vendor_specific_sampling


# Kept explicit and sorted; checked by tests/test_builders.py. A dir()-based
# list included imported names such as ``annotations``.
__all__ = [
    "ACTIVITY_TYPES",
    "ActivitiesType",
    "Activity",
    "ActivityDomainType",
    "ActivitySettingsType",
    "AssumptionType",
    "AxesType",
    "BoundaryType",
    "CalibrationTarget",
    "CalibrationType",
    "Cauchy",
    "CauchyTolerance",
    "ConvexHullType",
    "CoverageClassificationType",
    "CredibilityAssessmentType",
    "DISTRIBUTIONS",
    "DataSource",
    "DesiredResultsType",
    "Distribution",
    "Domain",
    "DomainCoverageType",
    "DomainsType",
    "ErrorMetric",
    "ExperimentPointsType",
    "ExternalDocumentType",
    "ForwardUncertaintyQuantificationType",
    "HyperRectangleType",
    "KeyValueType",
    "KeyValuesType",
    "LatinHypercubeType",
    "ModelType",
    "ModelingAssumptionsType",
    "MonotoneSplineCDF",
    "Normal",
    "NormalTolerance",
    "ObservedVariableType",
    "ObservedVariablesType",
    "OperationalDomainRefType",
    "OperationalDomainType",
    "OriginType",
    "ParameterSetType",
    "ParametersType",
    "PercentilesType",
    "PointsType",
    "ProcessContextType",
    "PseudoRandomType",
    "RESULT_DISTRIBUTIONS",
    "RealRangeType",
    "RealValueType",
    "ReferenceDataType",
    "Region",
    "RequiredAssumptionsType",
    "ResultItem",
    "ResultSetType",
    "ResultsCauchy",
    "ResultsCauchyTolerance",
    "ResultsMonotoneSplineCDF",
    "ResultsNormal",
    "ResultsNormalTolerance",
    "ResultsType",
    "ResultsUniform",
    "ResultsUniformTolerance",
    "ResultsWeibull",
    "Sampling",
    "SamplingMethodType",
    "SensitivityAnalysisType",
    "Shape",
    "SimulationSettingType",
    "SobolIndicesType",
    "SourceType",
    "StringValueType",
    "Study",
    "Tparameter",
    "Tunit",
    "TypedOperationalDomainKind",
    "TypedOperationalDomainType",
    "UncertainParameterType",
    "UncertaintyQuantification",
    "Uniform",
    "UniformTolerance",
    "UnitsType",
    "ValidationType",
    "VendorSpecificType",
    "VerificationType",
    "Weibull",
    "activities_of",
    "activity_domain",
    "activity_of",
    "add_activity",
    "add_domain",
    "assumption",
    "axes",
    "axis_names",
    "boundary",
    "calibration",
    "calibration_target",
    "convex_hull",
    "credibility_assessment",
    "desired_results",
    "distribution_of",
    "domain_coverage",
    "domains",
    "domains_of",
    "error_metric",
    "find_domain",
    "forward_uq",
    "hyper_rectangle",
    "model_info",
    "modeling_assumptions",
    "observed_names",
    "operational_domain",
    "points_of",
    "process_context",
    "reference_data",
    "required_assumptions",
    "result_items",
    "result_set",
    "results",
    "results_of",
    "sampling_of",
    "sensitivity_analysis",
    "shape_of",
    "simulation_setting",
    "study",
    "uncertain_parameter",
    "upsert_coverage",
    "validation",
    "verification",
]
