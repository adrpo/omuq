"""Three-level validation of omuq data inside an SSP package.

Level 1 (schema): host documents that carry omuq links, and every omuq
document, validate against the bundled XSD sets.

Level 2 (links): MetaData sources resolve inside the package, external
sources resolve and match their checksums, in-document references point at
existing ids, ids are unique, study names are unique per package.

Level 3 (model): parameter and observed-variable names resolve against the
anchor scope in the host SSD (or against the parameter names of the host
SSV for overlay anchors).

Every cross-reference attribute in the omuq schema is a plain ``xs:string``
rather than ``xs:IDREF``, so levels 2 and 3 are not covered by XSD
validation; they are implemented in this module.
"""

from __future__ import annotations

import dataclasses
import hashlib
import posixpath
from dataclasses import dataclass, field
from enum import Enum
from importlib import resources as _ilr
from typing import Literal

from lxml import etree

from .anchors import ElementAnchor, ParameterBindingAnchor, SsdRootAnchor, SsvAnchor
from .errors import LinkError, PackageError
from .model import (
    ObservedVariableType,
    UncertainParameterType,
)

# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

#: The severity of an :class:`Issue`.
Level = Literal["error", "warning", "info"]


@dataclass
class Issue:
    level: Level
    code: str
    message: str
    location: str = ""

    def __str__(self) -> str:  # pragma: no cover - convenience
        loc = f" [{self.location}]" if self.location else ""
        return f"{self.level.upper()} {self.code}: {self.message}{loc}"


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, level: Level, code: str, message: str, location: str = "") -> None:
        self.issues.append(Issue(level, code, message, location))

    def __str__(self) -> str:  # pragma: no cover - convenience
        if not self.issues:
            return "validation: OK (no issues)"
        return "\n".join(str(i) for i in self.issues)


# ---------------------------------------------------------------------------
# Level 1: XSD validation
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict[str, etree.XMLSchema] = {}

_SCHEMA_FILES = {
    "uq": ("uq", "UncertaintyQuantification.xsd"),
    "ssd": ("ssp", "SystemStructureDescription.xsd"),
    "ssv": ("ssp", "SystemStructureParameterValues.xsd"),
}


def _schema(kind: str) -> etree.XMLSchema:
    if kind not in _SCHEMA_CACHE:
        subdir, fname = _SCHEMA_FILES[kind]
        base = _ilr.files("omuq") / "schemas" / subdir
        with _ilr.as_file(base / fname) as path:
            _SCHEMA_CACHE[kind] = etree.XMLSchema(etree.parse(str(path)))
    return _SCHEMA_CACHE[kind]


def validate_xml(kind: str, data: bytes, location: str, report: ValidationReport):
    try:
        doc = etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        report.add("error", "L1.not-well-formed", str(exc), location)
        return
    schema = _schema(kind)
    if not schema.validate(doc):
        for err in schema.error_log:
            report.add(
                "error",
                "L1.schema",
                err.message,
                f"{location}:{err.line}",
            )


# ---------------------------------------------------------------------------
# Generic dataclass walking helpers
# ---------------------------------------------------------------------------


def _walk(obj, seen=None):
    """Depth-first over dataclass instances (including inside lists)."""
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        yield obj
        for f in dataclasses.fields(obj):
            yield from _walk(getattr(obj, f.name), seen)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk(item, seen)


def _collect_ids(doc) -> dict[str, int]:
    ids: dict[str, int] = {}
    for node in _walk(doc):
        val = getattr(node, "id", None)
        if isinstance(val, str) and val:
            ids[val] = ids.get(val, 0) + 1
    return ids


_REF_FIELDS = (
    "activity_domain_ref",
    "domain_ref",
    "parent_ref",
    "requested_domain_ref",
    "realized_domain_ref",
    "ref",  # OperationalDomainRefType
)


def _collect_refs(doc) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for node in _walk(doc):
        for fname in _REF_FIELDS:
            val = getattr(node, fname, None)
            if isinstance(val, str) and val:
                refs.append((type(node).__name__ + "." + fname, val))
    if isinstance(doc.required_assumptions_refs, str):
        for tok in doc.required_assumptions_refs.split():
            refs.append(("UncertaintyQuantification.requiredAssumptionsRefs", tok))
    return refs


def _collect_external_sources(doc) -> list[tuple[object, str]]:
    out = []
    for node in _walk(doc):
        src = getattr(node, "source", None)
        if (
            isinstance(src, str)
            and src
            and hasattr(node, "checksum")
            and hasattr(node, "source_base")
        ):
            out.append((node, src))
    return out


def _variable_names(doc) -> list[tuple[str, str]]:
    """(kind, name) for every name expected to denote a model variable."""
    out: list[tuple[str, str]] = []
    for node in _walk(doc):
        if isinstance(node, UncertainParameterType) and node.name:
            out.append(("uncertain-parameter", node.name))
        elif isinstance(node, ObservedVariableType) and node.name:
            out.append(("observed-variable", node.name))
        else:
            pname = getattr(node, "parameter_name", None)
            if isinstance(pname, str) and pname:
                out.append(("calibration-target", pname))
    return out


_HASHES = {
    "sha256": hashlib.sha256,
    "sha1": hashlib.sha1,
    "sha512": hashlib.sha512,
    "md5": hashlib.md5,
}


# ---------------------------------------------------------------------------
# Package-level validation
# ---------------------------------------------------------------------------


def validate_package(pkg, level: int = 3) -> ValidationReport:
    report = ValidationReport()
    try:
        studies = pkg.uq.studies()
    except (LinkError, PackageError) as exc:
        report.add("error", "L2.link", str(exc))
        return report

    touched_hosts: set[tuple[str, str]] = set()
    for s in studies:
        if isinstance(s.anchor, SsvAnchor):
            touched_hosts.add(("ssv", s.anchor.entry))
        else:
            touched_hosts.add(("ssd", s.anchor.ssd_name))

    if level >= 1:
        for kind, name in sorted(touched_hosts):
            validate_xml(kind, pkg.read(name), name, report)
        for s in studies:
            if s.entry is not None:
                validate_xml("uq", pkg.read(s.entry), s.entry, report)

    if level >= 2:
        _level2(pkg, studies, report)
    if level >= 3:
        _level3(pkg, studies, report)
    return report


def _level2(pkg, studies, report: ValidationReport) -> None:
    names: dict[str, int] = {}
    for s in studies:
        names[s.document.name] = names.get(s.document.name, 0) + 1
    for name, count in names.items():
        if count > 1:
            report.add(
                "error",
                "L2.duplicate-study-name",
                f"study name {name!r} is attached {count} times; names must "
                "be unique per package",
            )

    for s in studies:
        loc = s.entry or f"(inline at {s.anchor})"
        doc = s.document
        ids = _collect_ids(doc)
        for i, count in ids.items():
            if count > 1:
                report.add(
                    "error", "L2.duplicate-id", f"id {i!r} defined {count} times", loc
                )
        for origin, ref in _collect_refs(doc):
            if "#" in ref or "/" in ref:
                path = ref.split("#", 1)[0]
                if path:
                    try:
                        target = pkg.uq.resolve_source(s.entry or "", path)
                        pkg.read(target)
                    except (LinkError, PackageError):
                        report.add(
                            "error",
                            "L2.broken-ref",
                            f"{origin}={ref!r}: target file not found in package",
                            loc,
                        )
                        continue
                report.add(
                    "info",
                    "L2.cross-file-ref",
                    f"{origin}={ref!r}: fragment not verified (cross-file reference)",
                    loc,
                )
            elif ref not in ids:
                report.add(
                    "error",
                    "L2.broken-ref",
                    f"{origin}={ref!r} does not match any id in the document",
                    loc,
                )

        base = posixpath.dirname(s.entry) if s.entry else ""
        for node, src in _collect_external_sources(doc):
            if "://" in src:
                report.add(
                    "info",
                    "L2.absolute-uri",
                    f"external source {src!r} is an absolute URI and was not checked",
                    loc,
                )
                continue
            sb = getattr(node, "source_base", None)
            sb_val = sb.value if isinstance(sb, Enum) else sb
            if sb_val not in (None, "file"):
                report.add(
                    "warning",
                    "L2.source-base",
                    f"sourceBase={sb_val!r} is not supported by omuq-python "
                    "(only 'file' resolution is implemented)",
                    loc,
                )
                continue
            resolved = posixpath.normpath(posixpath.join(base, src))
            try:
                data = pkg.read(resolved)
            except PackageError:
                report.add(
                    "error",
                    "L2.missing-source",
                    f"external source {src!r} not found in package "
                    f"(resolved to {resolved!r})",
                    loc,
                )
                continue
            checksum = getattr(node, "checksum", None)
            ctype = getattr(node, "checksum_type", None)
            if checksum:
                algo = _HASHES.get((ctype or "sha256").replace("-", "").lower())
                if algo is None:
                    report.add(
                        "warning",
                        "L2.checksum-type",
                        f"unknown checksumType {ctype!r}; checksum not verified",
                        loc,
                    )
                elif algo(data).hexdigest().lower() != checksum.lower():
                    report.add(
                        "error",
                        "L2.checksum",
                        f"checksum mismatch for external source {src!r}",
                        loc,
                    )


def _level3(pkg, studies, report: ValidationReport) -> None:
    for s in studies:
        loc = s.entry or f"(inline at {s.anchor})"
        names = _variable_names(s.document)
        if isinstance(s.anchor, SsvAnchor):
            declared = pkg.ssv(s.anchor.entry).parameter_names()
            for kind, name in names:
                if kind == "observed-variable":
                    continue  # outputs are not SSV parameters
                if name not in declared:
                    report.add(
                        "warning",
                        "L3.unknown-parameter",
                        f"{kind} {name!r} does not match any parameter in "
                        f"{s.anchor.entry}",
                        loc,
                    )
            continue

        host = pkg.ssd(s.anchor.ssd_name)
        if isinstance(s.anchor, SsdRootAnchor):
            scope = host.root_system
        elif isinstance(s.anchor, (ElementAnchor, ParameterBindingAnchor)):
            scope = host.element_at(s.anchor.path)
        else:  # pragma: no cover - defensive
            continue
        for kind, name in names:
            verdict = host.resolve_variable(scope, name)
            if verdict == "bad":
                report.add(
                    "error",
                    "L3.bad-name",
                    f"{kind} {name!r} does not resolve to any element or "
                    "connector in the anchor scope",
                    loc,
                )
            elif verdict == "unknown":
                report.add(
                    "warning",
                    "L3.undeclared-variable",
                    f"{kind} {name!r} lands on a component but is not a "
                    "declared connector (it may still exist inside the FMU)",
                    loc,
                )
