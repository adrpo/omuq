"""omuq-python: attach, read, and validate omuq (openScaling UQ) data in SSP packages.

Example::

    from omuq import CsvSink, ElementAnchor, Simulation, SspPackage, model

    pkg = SspPackage.open("model.ssp")

    study = model.study(
        "BatteryUQ",
        activities=[
            model.forward_uq(
                uncertain=[
                    model.uncertain_parameter(
                        "R0", model.Normal(mu=0.05, sigma=0.005),
                        source="Measured",
                    )
                ],
                observed=["V"],
                samples=200,
            )
        ],
    )
    pkg.uq.attach(study, ElementAnchor(("battery",)))
    report = pkg.uq.validate()
    assert report.ok, str(report)
    pkg.save("model.uq.ssp")

    # Read the package back and simulate it.
    sim = Simulation.from_package("model.uq.ssp")
    sim.subscribe(CsvSink("run.csv"))
    sim.on_violation(print, only="Validation")
    result = sim.run()
    print(result.summary())
"""

from . import model
from ._xml import parse_study, serialize_study
from .anchors import (
    Anchor,
    ElementAnchor,
    ParameterBindingAnchor,
    SsdRootAnchor,
    SsvAnchor,
)
from .constants import (
    DEFAULT_KIND,
    MIME_ALIASES,
    MIME_OMUQ,
    UQ_RESOURCE_DIR,
)
from .constants import (
    TOOL_VERSION as __version__,
)
from .drivers import (
    DockerOMSimulatorDriver,
    FunctionDriver,
    OMSimulatorDriver,
    auto_driver,
)
from .errors import (
    AmbiguousPathError,
    AnchorError,
    DriverNotFoundError,
    DuplicateStudyError,
    FittingError,
    LinkError,
    ModelError,
    OmuqError,
    PackageError,
    SimulationError,
)
from .fitting import (
    fit_activity_domain,
    fit_boundary,
    fit_operational_domain,
    samples_from_csv,
)
from .package import AttachedStudy, SspPackage, UqManager
from .simulation import (
    CsvSink,
    DomainViolation,
    MemorySink,
    PrintSink,
    Sample,
    Simulation,
    SimulationDriver,
    SimulationResult,
    Sink,
    SkippedDomain,
)
from .validation import Issue, ValidationReport
from .webui import WebUi
from .writeback import RecordedResult, coverage_from_result
from .xmlhost import DefaultExperiment

__all__ = [
    "__version__",
    "Anchor",
    "AttachedStudy",
    "AmbiguousPathError",
    "AnchorError",
    "CsvSink",
    "DEFAULT_KIND",
    "DefaultExperiment",
    "DockerOMSimulatorDriver",
    "DomainViolation",
    "DriverNotFoundError",
    "DuplicateStudyError",
    "ElementAnchor",
    "FittingError",
    "FunctionDriver",
    "Issue",
    "LinkError",
    "MIME_ALIASES",
    "MIME_OMUQ",
    "MemorySink",
    "ModelError",
    "OMSimulatorDriver",
    "OmuqError",
    "PackageError",
    "ParameterBindingAnchor",
    "PrintSink",
    "RecordedResult",
    "Sample",
    "Simulation",
    "SimulationDriver",
    "SimulationError",
    "SimulationResult",
    "Sink",
    "SkippedDomain",
    "SsdRootAnchor",
    "SspPackage",
    "SsvAnchor",
    "UQ_RESOURCE_DIR",
    "UqManager",
    "ValidationReport",
    "WebUi",
    "auto_driver",
    "coverage_from_result",
    "fit_activity_domain",
    "fit_boundary",
    "fit_operational_domain",
    "model",
    "parse_study",
    "samples_from_csv",
    "serialize_study",
]
