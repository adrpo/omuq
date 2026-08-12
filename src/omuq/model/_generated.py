from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ForwardRef

from xsdata.models.datatype import XmlDateTime


@dataclass(kw_only=True)
class AxesType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    axis: list[AxesType.Axis] = field(
        default_factory=list,
        metadata={
            "name": "Axis",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class Axis:
        name: str = field(
            metadata={
                "type": "Attribute",
            }
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class ConvexHullType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    point: list[ConvexHullType.Point] = field(
        default_factory=list,
        metadata={
            "name": "Point",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class Point:
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        coordinates: str = field(
            metadata={
                "type": "Attribute",
            }
        )


class CoverageClassificationType(Enum):
    COVERED = "Covered"
    HIGH_RISK = "HighRisk"
    ACCEPTABLE_RISK = "AcceptableRisk"
    NOT_NEEDED = "NotNeeded"


@dataclass(kw_only=True)
class ExternalDocumentType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    source: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    section: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class HyperRectangleType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    point: list[HyperRectangleType.Point] = field(
        default_factory=list,
        metadata={
            "name": "Point",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            "max_occurs": 2,
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class Point:
        coordinates: str = field(
            metadata={
                "type": "Attribute",
            }
        )


@dataclass(kw_only=True)
class KeyValueType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    value: str = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class ObservedVariableType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    distribution_approximation: None | str = field(
        default=None,
        metadata={
            "name": "distributionApproximation",
            "type": "Attribute",
        },
    )
    unit: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class OperationalDomainRefType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    ref: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


class OriginType(Enum):
    REQUIREMENT = "requirement"
    STANDARD = "standard"
    DESIGN_DECISION = "design-decision"
    INHERITED = "inherited"
    EXPERT_JUDGMENT = "expert-judgment"
    EMPIRICAL = "empirical"
    LITERATURE = "literature"
    UNKNOWN = "unknown"


@dataclass(kw_only=True)
class PercentilesType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    level: list[float] = field(
        default_factory=list,
        metadata={
            "type": "Attribute",
            "tokens": True,
        },
    )


@dataclass(kw_only=True)
class PointsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    point: list[PointsType.Point] = field(
        default_factory=list,
        metadata={
            "name": "Point",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class Point:
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        coordinates: str = field(
            metadata={
                "type": "Attribute",
            }
        )


@dataclass(kw_only=True)
class RealRangeType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    low: float = field(
        metadata={
            "type": "Attribute",
        }
    )
    high: float = field(
        metadata={
            "type": "Attribute",
        }
    )
    unit: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class RealValueType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    value: float = field(
        metadata={
            "type": "Attribute",
        }
    )
    unit: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ReferenceDataType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    data_source: list[ReferenceDataType.DataSource] = field(
        default_factory=list,
        metadata={
            "name": "DataSource",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class DataSource:
        name: str = field(
            metadata={
                "type": "Attribute",
            }
        )
        file: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        type_value: None | str = field(
            default=None,
            metadata={
                "name": "type",
                "type": "Attribute",
            },
        )
        description: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class SobolIndicesType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    order: int = field(
        metadata={
            "type": "Attribute",
        }
    )
    total: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


class SourceType(Enum):
    UNKNOWN = "Unknown"
    ESTIMATED = "Estimated"
    PROVIDED = "Provided"
    COMPUTED = "Computed"
    MEASURED = "Measured"
    CALIBRATED = "Calibrated"


@dataclass(kw_only=True)
class StringValueType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    value: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


class TypedOperationalDomainKind(Enum):
    OPERATIONAL_DESIGN_DOMAIN = "OperationalDesignDomain"
    REQUESTED_OPERATIONAL_DOMAIN = "RequestedOperationalDomain"
    MODELED_OPERATIONAL_DOMAIN = "ModeledOperationalDomain"


@dataclass(kw_only=True)
class ContentType:
    """
    This optional element can contain inlined content of an entity.

    If it is present, then the attribute source of the enclosing element
    must not be present.

    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    :ivar content:
    """

    class Meta:
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
        },
    )


class MetaDataKind(Enum):
    GENERAL = "general"
    QUALITY = "quality"


class MetaDataSourceBase(Enum):
    FILE = "file"
    RESOURCE = "resource"


class SignatureTypeRole(Enum):
    AUTHENTICITY = "authenticity"
    SUITABILITY = "suitability"


class SignatureTypeSourceBase(Enum):
    FILE = "file"
    RESOURCE = "resource"
    META_DATA = "metaData"


@dataclass(kw_only=True)
class Tannotations:
    class Meta:
        name = "TAnnotations"
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    annotation: list[Tannotations.Annotation] = field(
        default_factory=list,
        metadata={
            "name": "Annotation",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            "min_occurs": 1,
        },
    )

    @dataclass(kw_only=True)
    class Annotation:
        """
        :ivar type_value: The unique name of the type of the annotation.
            In order to ensure uniqueness all types should be identified
            with reverse domain name notation (cf. Java package names or
            Apple UTIs) of a domain that is controlled by the entity
            defining the semantics and content of the annotation. For
            vendor-specific annotations this would e.g. be a domain
            controlled by the tool vendor. For MAP-SSP defined
            annotations, this will be a domain under the org.modelica
            prefix.
        :ivar content:
        """

        type_value: str = field(
            metadata={
                "name": "type",
                "type": "Attribute",
            }
        )
        content: list[object] = field(
            default_factory=list,
            metadata={
                "type": "Wildcard",
                "namespace": "##any",
                "mixed": True,
            },
        )


@dataclass(kw_only=True)
class ClassificationType:
    """
    :ivar classification_entry: A keyword value pair: the keyword is
        given by the 'keyword' attribute and the value is the element
        content.
    :ivar type_value:
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    """

    class Meta:
        target_namespace = (
            "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon"
        )

    classification_entry: list[ClassificationType.ClassificationEntry] = field(
        default_factory=list,
        metadata={
            "name": "ClassificationEntry",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class ClassificationEntry:
        """
        :ivar keyword:
        :ivar type_value:
        :ivar id: This attribute gives the model element a file-wide
            unique id which can be referenced from other elements or via
            URI fragment identifier.
        :ivar description:
        :ivar content:
        """

        keyword: str = field(
            metadata={
                "type": "Attribute",
            }
        )
        type_value: str = field(
            default="text/plain",
            metadata={
                "name": "type",
                "type": "Attribute",
            },
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        description: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        content: list[object] = field(
            default_factory=list,
            metadata={
                "type": "Wildcard",
                "namespace": "##any",
                "mixed": True,
            },
        )


@dataclass(kw_only=True)
class AssumptionType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    operational_domain_ref: list[OperationalDomainRefType] = field(
        default_factory=list,
        metadata={
            "name": "OperationalDomainRef",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    choice: (
        None
        | RealValueType
        | RealRangeType
        | StringValueType
        | str
        | ExternalDocumentType
    ) = field(
        default=None,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "Real",
                    "type": RealValueType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "RealRange",
                    "type": RealRangeType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "String",
                    "type": StringValueType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Text",
                    "type": str,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "ExternalDocument",
                    "type": ExternalDocumentType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    origin: None | OriginType = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    origin_ref: None | str = field(
        default=None,
        metadata={
            "name": "originRef",
            "type": "Attribute",
        },
    )
    valid_from: None | float = field(
        default=None,
        metadata={
            "name": "validFrom",
            "type": "Attribute",
        },
    )
    valid_to: None | float = field(
        default=None,
        metadata={
            "name": "validTo",
            "type": "Attribute",
        },
    )
    time_unit: None | str = field(
        default=None,
        metadata={
            "name": "timeUnit",
            "type": "Attribute",
        },
    )
    author: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    fileversion: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    copyright: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    license: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    generation_tool: None | str = field(
        default=None,
        metadata={
            "name": "generationTool",
            "type": "Attribute",
        },
    )
    generation_date_and_time: None | XmlDateTime = field(
        default=None,
        metadata={
            "name": "generationDateAndTime",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Axes(AxesType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class BoundaryType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    convex_hull_or_hyper_rectangle: (
        None | ConvexHullType | HyperRectangleType
    ) = field(
        default=None,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "ConvexHull",
                    "type": ConvexHullType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "HyperRectangle",
                    "type": HyperRectangleType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )


@dataclass(kw_only=True)
class ConvexHull(ConvexHullType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class CredibilityAssessmentType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    level: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    purpose: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    standard: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DesiredResultsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    percentiles: None | PercentilesType = field(
        default=None,
        metadata={
            "name": "Percentiles",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    sobol_indices: None | SobolIndicesType = field(
        default=None,
        metadata={
            "name": "SobolIndices",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    data: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    summary: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    scope: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    mean: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    standard_deviation: None | bool = field(
        default=None,
        metadata={
            "name": "standardDeviation",
            "type": "Attribute",
        },
    )
    histogram: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    pdf: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    cdf: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    quantile: None | bool = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class HyperRectangle(HyperRectangleType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class KeyValuesType:
    """
    :ivar key_value:
    :ivar type_value: The unique name of the type in reverse domain name
        notation.
    """

    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_value: list[KeyValueType] = field(
        default_factory=list,
        metadata={
            "name": "KeyValue",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    type_value: str = field(
        metadata={
            "name": "type",
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class ObservedVariablesType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    observed_variable: list[ObservedVariableType] = field(
        default_factory=list,
        metadata={
            "name": "ObservedVariable",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Points(PointsType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class ProcessContextType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    process: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    phase: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    glue_particle_ref: None | str = field(
        default=None,
        metadata={
            "name": "glueParticleRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SignatureType:
    """
    :ivar content:
    :ivar role: This mandatory attribute specifies the role this
        signature has in the overall process. It indicates whether the
        digital signature is intended to just convey the authenticity of
        the information, or whether a claim for suitability of the
        information for certain purposes is made.  In the later case,
        the digital signature format should include detailed information
        about what suitability claims are being made.
    :ivar type_value: This mandatory attribute specifies the MIME type
        of the resource signature, which does not have a default value.
        If no specific MIME type can be indicated, then the type
        application/octet-stream is to be used.
    :ivar source: This attribute indicates the source of the digital
        signature as a URI (cf. RFC 3986).  The base URI for the
        resolution of relative URIs is determined by the sourceBase
        attribute. If the source attribute is missing, the signature
        must be provided inline as contents of a Content element, which
        must not be present otherwise.
    :ivar source_base: Defines the base the source URI is resolved
        against:  If the attribute is missing or is specified as file,
        the source is resolved against the URI of the containing file.
        If the containing model element has a source attribute, the
        sourceBase attribute can be specified as resource. In this case
        the URI is resolved against the (resolved) source URI of the
        containing model element.  If the Signature element is contained
        within a MetaData element, the sourceBase attribute can be
        specified as metaData.  In this case the URI is resolved against
        the (resolved) URI of the meta data source. The last two options
        allow the specification of signature sources that reside inside
        a resource (for example an FMU), or the meta data through
        relative URIs.
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    """

    class Meta:
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    content: None | ContentType = field(
        default=None,
        metadata={
            "name": "Content",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    role: SignatureTypeRole = field(
        metadata={
            "type": "Attribute",
        }
    )
    type_value: str = field(
        metadata={
            "name": "type",
            "type": "Attribute",
        }
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source_base: SignatureTypeSourceBase = field(
        default=SignatureTypeSourceBase.FILE,
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Tenumeration:
    """
    :ivar item:
    :ivar annotations:
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    :ivar name: This attribute specifies the name of the enumeration in
        the system description, which must be unique within in the
        system description.
    """

    class Meta:
        name = "TEnumeration"
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    item: list[Tenumeration.Item] = field(
        default_factory=list,
        metadata={
            "name": "Item",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            "min_occurs": 1,
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )

    @dataclass(kw_only=True)
    class Item:
        """
        :ivar name: Name of the Enumeration Item
        :ivar value: The Value of the Enumeration Item
        """

        name: str = field(
            metadata={
                "type": "Attribute",
            }
        )
        value: int = field(
            metadata={
                "type": "Attribute",
            }
        )


@dataclass(kw_only=True)
class Tunit:
    """
    :ivar base_unit:
    :ivar annotations:
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    :ivar name: This attribute specifies the name of the unit in the
        system description, which must be unique within in the system
        description.
    """

    class Meta:
        name = "TUnit"
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    base_unit: Tunit.BaseUnit = field(
        metadata={
            "name": "BaseUnit",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        }
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )

    @dataclass(kw_only=True)
    class BaseUnit:
        """
        :ivar kg: Exponent of SI base unit "kg"
        :ivar m: Exponent of SI base unit "m"
        :ivar s: Exponent of SI base unit "s"
        :ivar a: Exponent of SI base unit "A"
        :ivar k: Exponent of SI base unit "K"
        :ivar mol: Exponent of SI base unit "mol"
        :ivar cd: Exponent of SI base unit "cd"
        :ivar rad: Exponent of SI derived unit "rad"
        :ivar factor:
        :ivar offset:
        """

        kg: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        m: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        s: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        a: int = field(
            default=0,
            metadata={
                "name": "A",
                "type": "Attribute",
            },
        )
        k: int = field(
            default=0,
            metadata={
                "name": "K",
                "type": "Attribute",
            },
        )
        mol: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        cd: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        rad: int = field(
            default=0,
            metadata={
                "type": "Attribute",
            },
        )
        factor: float = field(
            default=1.0,
            metadata={
                "type": "Attribute",
            },
        )
        offset: float = field(
            default=0.0,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class Tparameter:
    """
    :ivar choice:
    :ivar dimension: This optional element specifies one dimension of an
        array connector. If no dimension elements are present in a
        connector, it is a scalar connector. The number of dimension
        elements in a connector provides the dimensionality of the
        array. Either the size or the sizeConnector attributes CAN be
        present on the element, indicating a fixed size, or a size that
        depends on the structural parameter or constant referenced by
        the sizeConnector attribute. If none of the attributes are
        present, then the size of the dimension is unspecified at the
        SSD level. If both attributes are present this is considered an
        error.
    :ivar annotations:
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    :ivar name: This attribute specifies the name of the parameter in
        the parameter set, which must be unique within in the parameter
        set.
    """

    class Meta:
        name = "TParameter"
        target_namespace = (
            "http://ssp-standard.org/SSP1/SystemStructureParameterValues"
        )

    choice: (
        None
        | Tparameter.Real
        | Tparameter.Float64
        | Tparameter.Float32
        | Tparameter.Integer
        | Tparameter.Int8
        | Tparameter.Uint8
        | Tparameter.Int16
        | Tparameter.Uint16
        | Tparameter.Int32
        | Tparameter.Uint32
        | Tparameter.Int64
        | Tparameter.Uint64
        | Tparameter.Boolean
        | Tparameter.String
        | Tparameter.Enumeration
        | Tparameter.Binary
    ) = field(
        default=None,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "Real",
                    "type": ForwardRef("Tparameter.Real"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Float64",
                    "type": ForwardRef("Tparameter.Float64"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Float32",
                    "type": ForwardRef("Tparameter.Float32"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Integer",
                    "type": ForwardRef("Tparameter.Integer"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Int8",
                    "type": ForwardRef("Tparameter.Int8"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "UInt8",
                    "type": ForwardRef("Tparameter.Uint8"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Int16",
                    "type": ForwardRef("Tparameter.Int16"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "UInt16",
                    "type": ForwardRef("Tparameter.Uint16"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Int32",
                    "type": ForwardRef("Tparameter.Int32"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "UInt32",
                    "type": ForwardRef("Tparameter.Uint32"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Int64",
                    "type": ForwardRef("Tparameter.Int64"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "UInt64",
                    "type": ForwardRef("Tparameter.Uint64"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Boolean",
                    "type": ForwardRef("Tparameter.Boolean"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "String",
                    "type": ForwardRef("Tparameter.String"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Enumeration",
                    "type": ForwardRef("Tparameter.Enumeration"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
                {
                    "name": "Binary",
                    "type": ForwardRef("Tparameter.Binary"),
                    "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
                },
            ),
        },
    )
    dimension: list[Tparameter.Dimension] = field(
        default_factory=list,
        metadata={
            "name": "Dimension",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )

    @dataclass(kw_only=True)
    class Real:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        :ivar unit: This attribute gives the unit of the parameter value
            and must reference one of the unit definitions provided in
            the Units element of the enclosing file.
        """

        value: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Float64:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        :ivar unit: This attribute gives the unit of the parameter value
            and must reference one of the unit definitions provided in
            the Units element of the enclosing file.
        """

        value: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Float32:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        :ivar unit: This attribute gives the unit of the parameter value
            and must reference one of the unit definitions provided in
            the Units element of the enclosing file.
        """

        value: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Integer:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Int8:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Uint8:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Int16:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Uint16:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Int32:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Uint32:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Int64:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Uint64:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[int] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class Boolean:
        """
        :ivar value: This attribute gives the value(s) of the parameter.
            Array values are serialized in row-major order, as defined
            in FMI.
        """

        value: list[bool] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )

    @dataclass(kw_only=True)
    class String:
        """
        :ivar value: This element gives the value for one array element
            of the parameter. If any Value element is present, then the
            value attribute on the parent element MUST NOT be used.
            Array values are serialized in row-major order, as defined
            in FMI.
        :ivar value_attribute: This attribute gives the value of the
            parameter, if it is a scalar parameter. For array parameters
            requiring more than one element, Value elements MUST be
            used. For scalar and one element array parameters the Value
            element CAN be used. In either case, if Value elements are
            used, then this value attribute MUST NOT be present.
        """

        value: list[Tparameter.String.Value] = field(
            default_factory=list,
            metadata={
                "name": "Value",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
            },
        )
        value_attribute: None | str = field(
            default=None,
            metadata={
                "name": "value",
                "type": "Attribute",
            },
        )

        @dataclass(kw_only=True)
        class Value:
            value: str = field(
                metadata={
                    "type": "Attribute",
                }
            )

    @dataclass(kw_only=True)
    class Enumeration:
        """
        :ivar value: This element gives the value for one array element
            of the parameter as the enumeration item name. If any Value
            element is present, then the value attribute on the parent
            element MUST NOT be used. Note that the actual numeric value
            this value is mapped to at run time will depend on the item
            mapping of the enumeration type of the variables being
            parameterized. Array values are serialized in row-major
            order, as defined in FMI.
        :ivar value_attribute: This attribute gives the value of the
            parameter as the enumeration item name, if it is a scalar
            parameter. For array parameters requiring more than one
            element, Value elements MUST be used. For scalar and one
            element array parameters the Value element CAN be used. In
            either case, if Value elements are used, then this value
            attribute MUST NOT be present. Note that the actual numeric
            value this value is mapped to at run time will depend on the
            item mapping of the enumeration type of the variables being
            parameterized.
        :ivar name: This attribute specifies the name of the enumeration
            which references into the set of defined enumerations of the
            system structure description, as contained in the
            Enumerations element of the root element. This attribute is
            optional; if it is not specified, then the list of valid
            enumeration items with their names and values is not
            specified, and the interpretation of the enumeration value
            is left solely to the variables that are being
            parameterized. If the attribute is specified,
            implementations MAY use that information for user interface
            purposes, and/or for additional consistency checking.
        """

        value: list[Tparameter.Enumeration.Value] = field(
            default_factory=list,
            metadata={
                "name": "Value",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
            },
        )
        value_attribute: None | str = field(
            default=None,
            metadata={
                "name": "value",
                "type": "Attribute",
            },
        )
        name: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

        @dataclass(kw_only=True)
        class Value:
            value: str = field(
                metadata={
                    "type": "Attribute",
                }
            )

    @dataclass(kw_only=True)
    class Binary:
        """
        :ivar value: This element gives the value for one array element
            of the parameter. If any Value element is present, then the
            value attribute on the parent element MUST NOT be used.
            Array values are serialized in row-major order, as defined
            in FMI.
        :ivar mime_type: This optional attribute specifies the MIME type
            of the underlying binary data, which defaults to the non-
            specific application/octet-stream type.  This information
            can be used by the implementation to detect mismatches
            between binary parameters, or provide automatic conversions
            between different formats.  It should be noted that the
            implementation is not required to provide this service, i.e.
            it remains the responsibility of the operator to ensure only
            compatible binary connectors/parameters are connected.
        :ivar value_attribute: This attribute gives the value of the
            parameter as a hex encoded binary value, if it is a scalar
            parameter. For array parameters requiring more than one
            element, Value elements MUST be used. For scalar and one
            element array parameters the Value element CAN be used. In
            either case, if Value elements are used, then this value
            attribute MUST NOT be present.
        """

        value: list[Tparameter.Binary.Value] = field(
            default_factory=list,
            metadata={
                "name": "Value",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
            },
        )
        mime_type: str = field(
            default="application/octet-stream",
            metadata={
                "name": "mime-type",
                "type": "Attribute",
            },
        )
        value_attribute: None | bytes = field(
            default=None,
            metadata={
                "name": "value",
                "type": "Attribute",
                "format": "base16",
            },
        )

        @dataclass(kw_only=True)
        class Value:
            value: bytes = field(
                metadata={
                    "type": "Attribute",
                    "format": "base16",
                }
            )

    @dataclass(kw_only=True)
    class Dimension:
        """
        :ivar size: This attribute gives the size of this dimension of
            the connector as a fixed, unchangeable number.
        :ivar size_connector: This attribute references another
            connector by name, that gives the size of this dimension of
            the connector, e.g. a structural parameter or a constant of
            the underlying component that gives the dimension size.
        """

        size: None | int = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        size_connector: None | str = field(
            default=None,
            metadata={
                "name": "sizeConnector",
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class ActivitySettingsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_values: None | KeyValuesType = field(
        default=None,
        metadata={
            "name": "KeyValues",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    method: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DesiredResults(DesiredResultsType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class DomainCoverageType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    region: list[DomainCoverageType.Region] = field(
        default_factory=list,
        metadata={
            "name": "Region",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    requested_domain_ref: str = field(
        metadata={
            "name": "requestedDomainRef",
            "type": "Attribute",
        }
    )
    realized_domain_ref: str = field(
        metadata={
            "name": "realizedDomainRef",
            "type": "Attribute",
        }
    )

    @dataclass(kw_only=True)
    class Region:
        boundary: None | BoundaryType = field(
            default=None,
            metadata={
                "name": "Boundary",
                "type": "Element",
                "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            },
        )
        description: None | str = field(
            default=None,
            metadata={
                "name": "Description",
                "type": "Element",
                "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            },
        )
        classification: CoverageClassificationType = field(
            metadata={
                "type": "Attribute",
            }
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class LatinHypercubeType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_values: None | KeyValuesType = field(
        default=None,
        metadata={
            "name": "KeyValues",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    number_of_samples: int = field(
        metadata={
            "name": "numberOfSamples",
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class ModelingAssumptionsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    assumption: list[AssumptionType] = field(
        default_factory=list,
        metadata={
            "name": "Assumption",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            "min_occurs": 1,
        },
    )
    id: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    author: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    fileversion: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    copyright: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    license: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    generation_tool: None | str = field(
        default=None,
        metadata={
            "name": "generationTool",
            "type": "Attribute",
        },
    )
    generation_date_and_time: None | XmlDateTime = field(
        default=None,
        metadata={
            "name": "generationDateAndTime",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ObservedVariables(ObservedVariablesType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class PseudoRandomType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_values: None | KeyValuesType = field(
        default=None,
        metadata={
            "name": "KeyValues",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    number_of_samples: int = field(
        metadata={
            "name": "numberOfSamples",
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class RequiredAssumptionsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    assumption: list[AssumptionType] = field(
        default_factory=list,
        metadata={
            "name": "Assumption",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            "min_occurs": 1,
        },
    )
    id: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    author: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    fileversion: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    copyright: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    license: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    generation_tool: None | str = field(
        default=None,
        metadata={
            "name": "generationTool",
            "type": "Attribute",
        },
    )
    generation_date_and_time: None | XmlDateTime = field(
        default=None,
        metadata={
            "name": "generationDateAndTime",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SimulationSettingType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_values: None | KeyValuesType = field(
        default=None,
        metadata={
            "name": "KeyValues",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    stop_time: None | float = field(
        default=None,
        metadata={
            "name": "stopTime",
            "type": "Attribute",
        },
    )
    interval: None | float = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    tolerance: None | float = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    method: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class UnitsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    unit: list[Tunit] = field(
        default_factory=list,
        metadata={
            "name": "Unit",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class VendorSpecificType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    key_values: None | KeyValuesType = field(
        default=None,
        metadata={
            "name": "KeyValues",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )


@dataclass(kw_only=True)
class Tenumerations:
    class Meta:
        name = "TEnumerations"
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    enumeration: list[Tenumeration] = field(
        default_factory=list,
        metadata={
            "name": "Enumeration",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class Tunits:
    class Meta:
        name = "TUnits"
        target_namespace = "http://ssp-standard.org/SSP1/SystemStructureCommon"

    unit: list[Tunit] = field(
        default_factory=list,
        metadata={
            "name": "Unit",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class Tparameters:
    class Meta:
        name = "TParameters"
        target_namespace = (
            "http://ssp-standard.org/SSP1/SystemStructureParameterValues"
        )

    parameter: list[Tparameter] = field(
        default_factory=list,
        metadata={
            "name": "Parameter",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureParameterValues",
        },
    )


@dataclass(kw_only=True)
class ModelType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    modeling_assumptions: list[ModelingAssumptionsType] = field(
        default_factory=list,
        metadata={
            "name": "ModelingAssumptions",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    file: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    model: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    model_resource_meta_data: None | str = field(
        default=None,
        metadata={
            "name": "modelResourceMetaData",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ResultsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    choice: list[
        ResultsType.Normal
        | ResultsType.NormalTolerance
        | ResultsType.Uniform
        | ResultsType.UniformTolerance
        | ResultsType.Weibull
        | ResultsType.Cauchy
        | ResultsType.CauchyTolerance
        | ResultsType.MonotoneSplineCdf
        | VendorSpecificType
        | ResultsType.ErrorMetric
    ] = field(
        default_factory=list,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "Normal",
                    "type": ForwardRef("ResultsType.Normal"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "NormalTolerance",
                    "type": ForwardRef("ResultsType.NormalTolerance"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Uniform",
                    "type": ForwardRef("ResultsType.Uniform"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "UniformTolerance",
                    "type": ForwardRef("ResultsType.UniformTolerance"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Weibull",
                    "type": ForwardRef("ResultsType.Weibull"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Cauchy",
                    "type": ForwardRef("ResultsType.Cauchy"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "CauchyTolerance",
                    "type": ForwardRef("ResultsType.CauchyTolerance"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "MonotoneSplineCDF",
                    "type": ForwardRef("ResultsType.MonotoneSplineCdf"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "VendorSpecificDistribution",
                    "type": VendorSpecificType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "ErrorMetric",
                    "type": ForwardRef("ResultsType.ErrorMetric"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )
    point: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class ErrorMetric:
        name: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        type_value: str = field(
            metadata={
                "name": "type",
                "type": "Attribute",
            }
        )
        value: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        threshold: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        pass_value: None | bool = field(
            default=None,
            metadata={
                "name": "pass",
                "type": "Attribute",
            },
        )
        observed_variable: None | str = field(
            default=None,
            metadata={
                "name": "observedVariable",
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Normal:
        mu: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        sigma: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        minimum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class NormalTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        sigma_factor: float = field(
            default=3.0,
            metadata={
                "name": "sigmaFactor",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Uniform:
        minimum: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        maximum: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class UniformTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Weibull:
        shape: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        scale: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Cauchy:
        x0: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        gamma: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        minimum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class CauchyTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        boundary_probability: float = field(
            default=0.997,
            metadata={
                "name": "boundaryProbability",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class MonotoneSplineCdf:
        x: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        y: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        degree: int = field(
            default=3,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class SamplingMethodType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    pseudo_random_or_latin_hyper_cube_or_vendor_specific_sampling: (
        None | PseudoRandomType | LatinHypercubeType | VendorSpecificType
    ) = field(
        default=None,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "PseudoRandom",
                    "type": PseudoRandomType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "LatinHyperCube",
                    "type": LatinHypercubeType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "VendorSpecificSampling",
                    "type": VendorSpecificType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SimulationSetting(SimulationSettingType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class UncertainParameterType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    choice: (
        None
        | UncertainParameterType.Normal
        | UncertainParameterType.NormalTolerance
        | UncertainParameterType.Uniform
        | UncertainParameterType.UniformTolerance
        | UncertainParameterType.Weibull
        | UncertainParameterType.Cauchy
        | UncertainParameterType.CauchyTolerance
        | UncertainParameterType.MonotoneSplineCdf
        | VendorSpecificType
    ) = field(
        default=None,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "Normal",
                    "type": ForwardRef("UncertainParameterType.Normal"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "NormalTolerance",
                    "type": ForwardRef(
                        "UncertainParameterType.NormalTolerance"
                    ),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Uniform",
                    "type": ForwardRef("UncertainParameterType.Uniform"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "UniformTolerance",
                    "type": ForwardRef(
                        "UncertainParameterType.UniformTolerance"
                    ),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Weibull",
                    "type": ForwardRef("UncertainParameterType.Weibull"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Cauchy",
                    "type": ForwardRef("UncertainParameterType.Cauchy"),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "CauchyTolerance",
                    "type": ForwardRef(
                        "UncertainParameterType.CauchyTolerance"
                    ),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "MonotoneSplineCDF",
                    "type": ForwardRef(
                        "UncertainParameterType.MonotoneSplineCdf"
                    ),
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "VendorSpecificDistribution",
                    "type": VendorSpecificType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | SourceType = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source_info: None | str = field(
        default=None,
        metadata={
            "name": "sourceInfo",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class Normal:
        mu: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        sigma: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        minimum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class NormalTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        sigma_factor: float = field(
            default=3.0,
            metadata={
                "name": "sigmaFactor",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Uniform:
        minimum: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        maximum: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class UniformTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Weibull:
        shape: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        scale: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class Cauchy:
        x0: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        gamma: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        minimum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        maximum: None | float = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class CauchyTolerance:
        nominal: float = field(
            metadata={
                "type": "Attribute",
            }
        )
        rel_tol: float = field(
            default=0.0,
            metadata={
                "name": "relTol",
                "type": "Attribute",
            },
        )
        abs_tol: float = field(
            default=0.0,
            metadata={
                "name": "absTol",
                "type": "Attribute",
            },
        )
        boundary_probability: float = field(
            default=0.997,
            metadata={
                "name": "boundaryProbability",
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )

    @dataclass(kw_only=True)
    class MonotoneSplineCdf:
        x: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        y: list[float] = field(
            default_factory=list,
            metadata={
                "type": "Attribute",
                "tokens": True,
            },
        )
        degree: int = field(
            default=3,
            metadata={
                "type": "Attribute",
            },
        )
        unit: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class Units(UnitsType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class ParameterSet:
    """
    :ivar parameters:
    :ivar enumerations:
    :ivar units:
    :ivar meta_data: This element can specify additional meta data for
        the given resource. Multiple (or no) MetaData elements may be
        present.
    :ivar signature: This element can contain digital signature
        information on the data referenced by the enclosing element. It
        is left unspecified what types of signatures are used and/or
        available for now.  Multiple or no signature elements may be
        present.
    :ivar annotations:
    :ivar version: Version of SSV format, 1.0 or 2.0 for this release.
    :ivar id: This attribute gives the model element a file-wide unique
        id which can be referenced from other elements or via URI
        fragment identifier.
    :ivar description:
    :ivar name: Name of the Parameter Set.
    :ivar author:
    :ivar fileversion:
    :ivar copyright:
    :ivar license:
    :ivar generation_tool:
    :ivar generation_date_and_time:
    """

    class Meta:
        namespace = (
            "http://ssp-standard.org/SSP1/SystemStructureParameterValues"
        )

    parameters: Tparameters = field(
        metadata={
            "name": "Parameters",
            "type": "Element",
        }
    )
    enumerations: None | Tenumerations = field(
        default=None,
        metadata={
            "name": "Enumerations",
            "type": "Element",
        },
    )
    units: None | Tunits = field(
        default=None,
        metadata={
            "name": "Units",
            "type": "Element",
        },
    )
    meta_data: list[ParameterSet.MetaData] = field(
        default_factory=list,
        metadata={
            "name": "MetaData",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    signature: list[SignatureType] = field(
        default_factory=list,
        metadata={
            "name": "Signature",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
        },
    )
    version: str = field(
        metadata={
            "type": "Attribute",
            "pattern": r"1[.]0|2[.]0",
        }
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    author: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    fileversion: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    copyright: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    license: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    generation_tool: None | str = field(
        default=None,
        metadata={
            "name": "generationTool",
            "type": "Attribute",
        },
    )
    generation_date_and_time: None | XmlDateTime = field(
        default=None,
        metadata={
            "name": "generationDateAndTime",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class MetaData:
        """
        :ivar content: This optional element can contain inlined content
            of the resource meta data. If it is present, then the
            attribute source of the MetaData element must not be
            present.
        :ivar signature: This element can contain digital signature
            information on the data referenced by the enclosing element.
            It is left unspecified what types of signatures are used
            and/or available for now.  Multiple or no signature elements
            may be present.
        :ivar kind: This attribute indicates the kind of resource meta
            data that is referenced, i.e. what role it plays in relation
            to the resource being described.
        :ivar type_value: This mandatory attribute specifies the MIME
            type of the resource meta data, which does not have a
            default value.  If no specific MIME type can be indicated,
            then the type application/octet-stream is to be used.
        :ivar source: This attribute indicates the source of the
            resource meta data as a URI (cf. RFC 3986).  The base URI
            for the resolution of relative URIs is determined by the
            sourceBase attribute. If the source attribute is missing,
            the meta data is provided inline as contents of a Content
            element, which must not be present otherwise.
        :ivar source_base: Defines the base the source URI is resolved
            against:  If the attribute is missing or is specified as
            file, the source is resolved against the URI of the
            containing file.  If the containing model element has a
            source attribute, the sourceBase attribute can be specified
            as resource. In this case the URI is resolved against the
            (resolved) source URI of the containing model element. The
            last option allows the specification of meta data sources
            that reside inside a resource (for example an FMU) through
            relative URIs.
        :ivar id: This attribute gives the model element a file-wide
            unique id which can be referenced from other elements or via
            URI fragment identifier.
        :ivar description:
        """

        content: None | ContentType = field(
            default=None,
            metadata={
                "name": "Content",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            },
        )
        signature: list[SignatureType] = field(
            default_factory=list,
            metadata={
                "name": "Signature",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            },
        )
        kind: MetaDataKind = field(
            metadata={
                "type": "Attribute",
            }
        )
        type_value: str = field(
            metadata={
                "name": "type",
                "type": "Attribute",
            }
        )
        source: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        source_base: MetaDataSourceBase = field(
            default=MetaDataSourceBase.FILE,
            metadata={
                "name": "sourceBase",
                "type": "Attribute",
            },
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        description: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class ParametersType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter: list[Tparameter] = field(
        default_factory=list,
        metadata={
            "name": "Parameter",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    uncertain_parameter: list[UncertainParameterType] = field(
        default_factory=list,
        metadata={
            "name": "UncertainParameter",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    source: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    type_value: None | str = field(
        default=None,
        metadata={
            "name": "type",
            "type": "Attribute",
        },
    )
    source_base: str = field(
        default="file",
        metadata={
            "name": "sourceBase",
            "type": "Attribute",
        },
    )
    checksum: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    checksum_type: None | str = field(
        default=None,
        metadata={
            "name": "checksumType",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ResultSetType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    results: list[ResultsType] = field(
        default_factory=list,
        metadata={
            "name": "Results",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )


@dataclass(kw_only=True)
class SamplingMethod(SamplingMethodType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class ExperimentPointsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    point_set: list[ExperimentPointsType.PointSet] = field(
        default_factory=list,
        metadata={
            "name": "PointSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )

    @dataclass(kw_only=True)
    class PointSet:
        points: PointsType = field(
            metadata={
                "name": "Points",
                "type": "Element",
                "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            }
        )
        parameters: None | ParametersType = field(
            default=None,
            metadata={
                "name": "Parameters",
                "type": "Element",
                "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
            },
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class Parameters(ParametersType):
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"


@dataclass(kw_only=True)
class ActivityDomainType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    axes: None | AxesType = field(
        default=None,
        metadata={
            "name": "Axes",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    boundary: None | BoundaryType = field(
        default=None,
        metadata={
            "name": "Boundary",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    experiment_points: None | ExperimentPointsType = field(
        default=None,
        metadata={
            "name": "ExperimentPoints",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    settings: None | ActivitySettingsType = field(
        default=None,
        metadata={
            "name": "Settings",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    id: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    kind: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "domainRef",
            "type": "Attribute",
        },
    )
    srmd_ref: None | str = field(
        default=None,
        metadata={
            "name": "srmdRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class OperationalDomainType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    axes: AxesType = field(
        metadata={
            "name": "Axes",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        }
    )
    boundary: BoundaryType = field(
        metadata={
            "name": "Boundary",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        }
    )
    experiment_points: None | ExperimentPointsType = field(
        default=None,
        metadata={
            "name": "ExperimentPoints",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    purpose: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TypedOperationalDomainType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    axes: None | AxesType = field(
        default=None,
        metadata={
            "name": "Axes",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    boundary: None | BoundaryType = field(
        default=None,
        metadata={
            "name": "Boundary",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    experiment_points: None | ExperimentPointsType = field(
        default=None,
        metadata={
            "name": "ExperimentPoints",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    credibility_assessment: None | CredibilityAssessmentType = field(
        default=None,
        metadata={
            "name": "CredibilityAssessment",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    process_context: None | ProcessContextType = field(
        default=None,
        metadata={
            "name": "ProcessContext",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "name": "Description",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    id: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    kind: TypedOperationalDomainKind = field(
        metadata={
            "type": "Attribute",
        }
    )
    geometry_kind: None | str = field(
        default=None,
        metadata={
            "name": "geometryKind",
            "type": "Attribute",
        },
    )
    parent_ref: None | str = field(
        default=None,
        metadata={
            "name": "parentRef",
            "type": "Attribute",
        },
    )
    srmd_ref: None | str = field(
        default=None,
        metadata={
            "name": "srmdRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DomainsType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    typed_operational_domain: list[TypedOperationalDomainType] = field(
        default_factory=list,
        metadata={
            "name": "TypedOperationalDomain",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    activity_domain: list[ActivityDomainType] = field(
        default_factory=list,
        metadata={
            "name": "ActivityDomain",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    domain_coverage: list[DomainCoverageType] = field(
        default_factory=list,
        metadata={
            "name": "DomainCoverage",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )


@dataclass(kw_only=True)
class ParameterSetType:
    """
    :ivar parameters:
    :ivar operational_domain:
    :ivar enumerations:
    :ivar units:
    :ivar meta_data: This element can specify additional meta data for
        the given resource. Multiple (or no) MetaData elements may be
        present.
    :ivar signature: This element can contain digital signature
        information on the data referenced by the enclosing element. It
        is left unspecified what types of signatures are used and/or
        available for now.  Multiple or no signature elements may be
        present.
    :ivar annotations:
    :ivar id:
    :ivar description:
    """

    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameters: None | ParametersType = field(
        default=None,
        metadata={
            "name": "Parameters",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    operational_domain: None | OperationalDomainType = field(
        default=None,
        metadata={
            "name": "OperationalDomain",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    enumerations: None | Tenumerations = field(
        default=None,
        metadata={
            "name": "Enumerations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    units: None | UnitsType = field(
        default=None,
        metadata={
            "name": "Units",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    meta_data: list[ParameterSetType.MetaData] = field(
        default_factory=list,
        metadata={
            "name": "MetaData",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    signature: list[SignatureType] = field(
        default_factory=list,
        metadata={
            "name": "Signature",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class MetaData:
        """
        :ivar content: This optional element can contain inlined content
            of the resource meta data. If it is present, then the
            attribute source of the MetaData element must not be
            present.
        :ivar signature: This element can contain digital signature
            information on the data referenced by the enclosing element.
            It is left unspecified what types of signatures are used
            and/or available for now.  Multiple or no signature elements
            may be present.
        :ivar kind: This attribute indicates the kind of resource meta
            data that is referenced, i.e. what role it plays in relation
            to the resource being described.
        :ivar type_value: This mandatory attribute specifies the MIME
            type of the resource meta data, which does not have a
            default value.  If no specific MIME type can be indicated,
            then the type application/octet-stream is to be used.
        :ivar source: This attribute indicates the source of the
            resource meta data as a URI (cf. RFC 3986).  The base URI
            for the resolution of relative URIs is determined by the
            sourceBase attribute. If the source attribute is missing,
            the meta data is provided inline as contents of a Content
            element, which must not be present otherwise.
        :ivar source_base: Defines the base the source URI is resolved
            against:  If the attribute is missing or is specified as
            file, the source is resolved against the URI of the
            containing file.  If the containing model element has a
            source attribute, the sourceBase attribute can be specified
            as resource. In this case the URI is resolved against the
            (resolved) source URI of the containing model element. The
            last option allows the specification of meta data sources
            that reside inside a resource (for example an FMU) through
            relative URIs.
        :ivar id: This attribute gives the model element a file-wide
            unique id which can be referenced from other elements or via
            URI fragment identifier.
        :ivar description:
        """

        content: None | ContentType = field(
            default=None,
            metadata={
                "name": "Content",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            },
        )
        signature: list[SignatureType] = field(
            default_factory=list,
            metadata={
                "name": "Signature",
                "type": "Element",
                "namespace": "http://ssp-standard.org/SSP1/SystemStructureCommon",
            },
        )
        kind: MetaDataKind = field(
            metadata={
                "type": "Attribute",
            }
        )
        type_value: str = field(
            metadata={
                "name": "type",
                "type": "Attribute",
            }
        )
        source: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        source_base: MetaDataSourceBase = field(
            default=MetaDataSourceBase.FILE,
            metadata={
                "name": "sourceBase",
                "type": "Attribute",
            },
        )
        id: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )
        description: None | str = field(
            default=None,
            metadata={
                "type": "Attribute",
            },
        )


@dataclass(kw_only=True)
class CalibrationType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter_set: None | ParameterSetType = field(
        default=None,
        metadata={
            "name": "ParameterSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    observed_variables: None | ObservedVariablesType = field(
        default=None,
        metadata={
            "name": "ObservedVariables",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    simulation_setting: None | SimulationSettingType = field(
        default=None,
        metadata={
            "name": "SimulationSetting",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    reference_data: None | ReferenceDataType = field(
        default=None,
        metadata={
            "name": "ReferenceData",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    calibration_targets: None | CalibrationType.CalibrationTargets = field(
        default=None,
        metadata={
            "name": "CalibrationTargets",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    activity_domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "activityDomainRef",
            "type": "Attribute",
        },
    )

    @dataclass(kw_only=True)
    class CalibrationTargets:
        target: list[CalibrationType.CalibrationTargets.Target] = field(
            default_factory=list,
            metadata={
                "name": "Target",
                "type": "Element",
                "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                "min_occurs": 1,
            },
        )

        @dataclass(kw_only=True)
        class Target:
            parameter_name: str = field(
                metadata={
                    "name": "parameterName",
                    "type": "Attribute",
                }
            )
            initial_value: None | float = field(
                default=None,
                metadata={
                    "name": "initialValue",
                    "type": "Attribute",
                },
            )
            lower_bound: None | float = field(
                default=None,
                metadata={
                    "name": "lowerBound",
                    "type": "Attribute",
                },
            )
            upper_bound: None | float = field(
                default=None,
                metadata={
                    "name": "upperBound",
                    "type": "Attribute",
                },
            )
            unit: None | str = field(
                default=None,
                metadata={
                    "type": "Attribute",
                },
            )


@dataclass(kw_only=True)
class ForwardUncertaintyQuantificationType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter_set: None | ParameterSetType = field(
        default=None,
        metadata={
            "name": "ParameterSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    observed_variables: None | ObservedVariablesType = field(
        default=None,
        metadata={
            "name": "ObservedVariables",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    desired_results: None | DesiredResultsType = field(
        default=None,
        metadata={
            "name": "DesiredResults",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    simulation_setting: None | SimulationSettingType = field(
        default=None,
        metadata={
            "name": "SimulationSetting",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    sampling_method: None | SamplingMethodType = field(
        default=None,
        metadata={
            "name": "SamplingMethod",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    activity_domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "activityDomainRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SensitivityAnalysisType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter_set: None | ParameterSetType = field(
        default=None,
        metadata={
            "name": "ParameterSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    observed_variables: None | ObservedVariablesType = field(
        default=None,
        metadata={
            "name": "ObservedVariables",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    desired_results: None | DesiredResultsType = field(
        default=None,
        metadata={
            "name": "DesiredResults",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    simulation_setting: None | SimulationSettingType = field(
        default=None,
        metadata={
            "name": "SimulationSetting",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    sampling_method: None | SamplingMethodType = field(
        default=None,
        metadata={
            "name": "SamplingMethod",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    activity_domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "activityDomainRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ValidationType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter_set: None | ParameterSetType = field(
        default=None,
        metadata={
            "name": "ParameterSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    observed_variables: None | ObservedVariablesType = field(
        default=None,
        metadata={
            "name": "ObservedVariables",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    desired_results: None | DesiredResultsType = field(
        default=None,
        metadata={
            "name": "DesiredResults",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    simulation_setting: None | SimulationSettingType = field(
        default=None,
        metadata={
            "name": "SimulationSetting",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    sampling_method: None | SamplingMethodType = field(
        default=None,
        metadata={
            "name": "SamplingMethod",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    reference_data: None | ReferenceDataType = field(
        default=None,
        metadata={
            "name": "ReferenceData",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    activity_domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "activityDomainRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class VerificationType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    parameter_set: None | ParameterSetType = field(
        default=None,
        metadata={
            "name": "ParameterSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    observed_variables: None | ObservedVariablesType = field(
        default=None,
        metadata={
            "name": "ObservedVariables",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    desired_results: None | DesiredResultsType = field(
        default=None,
        metadata={
            "name": "DesiredResults",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    simulation_setting: None | SimulationSettingType = field(
        default=None,
        metadata={
            "name": "SimulationSetting",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    sampling_method: None | SamplingMethodType = field(
        default=None,
        metadata={
            "name": "SamplingMethod",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    reference_data: None | ReferenceDataType = field(
        default=None,
        metadata={
            "name": "ReferenceData",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    result_set: None | ResultSetType = field(
        default=None,
        metadata={
            "name": "ResultSet",
            "type": "Element",
            "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    description: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    activity_domain_ref: None | str = field(
        default=None,
        metadata={
            "name": "activityDomainRef",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class ActivitiesType:
    class Meta:
        target_namespace = (
            "http://openscaling.org/UQ1/UncertaintyQuantification"
        )

    choice: list[
        VerificationType
        | CalibrationType
        | ValidationType
        | SensitivityAnalysisType
        | ForwardUncertaintyQuantificationType
    ] = field(
        default_factory=list,
        metadata={
            "type": "Elements",
            "choices": (
                {
                    "name": "Verification",
                    "type": VerificationType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Calibration",
                    "type": CalibrationType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "Validation",
                    "type": ValidationType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "SensitivityAnalysis",
                    "type": SensitivityAnalysisType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
                {
                    "name": "ForwardUncertaintyQuantification",
                    "type": ForwardUncertaintyQuantificationType,
                    "namespace": "http://openscaling.org/UQ1/UncertaintyQuantification",
                },
            ),
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    credibility_level: None | str = field(
        default=None,
        metadata={
            "name": "credibilityLevel",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class UncertaintyQuantification:
    class Meta:
        namespace = "http://openscaling.org/UQ1/UncertaintyQuantification"

    required_assumptions: list[RequiredAssumptionsType] = field(
        default_factory=list,
        metadata={
            "name": "RequiredAssumptions",
            "type": "Element",
        },
    )
    domains: None | DomainsType = field(
        default=None,
        metadata={
            "name": "Domains",
            "type": "Element",
        },
    )
    model: None | ModelType = field(
        default=None,
        metadata={
            "name": "Model",
            "type": "Element",
        },
    )
    activities: None | ActivitiesType = field(
        default=None,
        metadata={
            "name": "Activities",
            "type": "Element",
        },
    )
    classification: list[ClassificationType] = field(
        default_factory=list,
        metadata={
            "name": "Classification",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    annotations: None | Tannotations = field(
        default=None,
        metadata={
            "name": "Annotations",
            "type": "Element",
            "namespace": "http://ssp-standard.org/SSPTraceability1/SSPTraceabilityCommon",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
    author: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    fileversion: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    copyright: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    license: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    generation_tool: None | str = field(
        default=None,
        metadata={
            "name": "generationTool",
            "type": "Attribute",
        },
    )
    generation_date_and_time: None | XmlDateTime = field(
        default=None,
        metadata={
            "name": "generationDateAndTime",
            "type": "Attribute",
        },
    )
    info: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    required_assumptions_refs: None | str = field(
        default=None,
        metadata={
            "name": "requiredAssumptionsRefs",
            "type": "Attribute",
        },
    )
    stmd_ref: None | str = field(
        default=None,
        metadata={
            "name": "stmdRef",
            "type": "Attribute",
        },
    )
    srmd_ref: None | str = field(
        default=None,
        metadata={
            "name": "srmdRef",
            "type": "Attribute",
        },
    )
