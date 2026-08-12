"""lxml editing layer for SSP host documents (SSD and SSV).

Host documents are third-party content and may carry vendor annotations,
comments, and formatting that must be preserved. This module does not
re-model a host document. It parses it with lxml, performs the minimal
edit (insert or remove one ``ssc:MetaData`` node, stamp the ``version``
attribute) and serializes the same tree back.

The insertion position is schema-constrained. The XSD content models
(verified against the official SSP 2.0 schemas) are:

* ``SystemStructureDescription``:
  ``System, Enumerations?, Units?, DefaultExperiment?, MetaData*, Signature*,
  Annotations?``
* ``TElement`` (``System``/``Component``/``SignalDictionaryReference``):
  ``Connectors?, ElementGeometry?, ParameterBindings?, MetaData*, Signature*``
  followed by the subtype extension children (``Elements`` etc. for systems,
  ``Annotations?`` for all subtypes).
* ``ParameterBinding``:
  ``ParameterValues?, ParameterMapping?, MetaData*, Signature*, Annotations?``
* SSV ``ParameterSet``:
  ``Parameters, Enumerations?, Units?, MetaData*, Signature*, Annotations?``

A new ``MetaData`` node is inserted after the last existing predecessor or
``MetaData`` sibling, which is correct for all four carriers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from lxml import etree

from .constants import NS_SSC, NS_SSD, NS_SSV, SSP_VERSION
from .errors import AmbiguousPathError, AnchorError, PackageError

Q_METADATA = f"{{{NS_SSC}}}MetaData"
Q_SIGNATURE = f"{{{NS_SSC}}}Signature"
Q_CONTENT = f"{{{NS_SSC}}}Content"

#: The four legal ``ssc:MetaData`` carriers (see the module docstring).
CarrierKind = Literal["ssd_root", "element", "binding", "ssv_root"]

#: The three outcomes of :meth:`SsdDocument.resolve_variable`.
Verdict = Literal["resolved", "unknown", "bad"]

#: The second element of an :meth:`SsdDocument.iter_carriers` triple: ``None``
#: for the SSD root, an element path for an element carrier, or ``(path,
#: index)`` for a parameter binding carrier.
CarrierPath = tuple[str, ...] | tuple[tuple[str, ...], int] | None

_PREDS: dict[CarrierKind, set[str]] = {
    "ssd_root": {
        f"{{{NS_SSD}}}System",
        f"{{{NS_SSD}}}Enumerations",
        f"{{{NS_SSD}}}Units",
        f"{{{NS_SSD}}}DefaultExperiment",
    },
    "element": {
        f"{{{NS_SSD}}}Connectors",
        f"{{{NS_SSD}}}ElementGeometry",
        f"{{{NS_SSD}}}ParameterBindings",
    },
    "binding": {
        f"{{{NS_SSD}}}ParameterValues",
        f"{{{NS_SSD}}}ParameterMapping",
    },
    "ssv_root": {
        f"{{{NS_SSV}}}Parameters",
        f"{{{NS_SSV}}}Enumerations",
        f"{{{NS_SSV}}}Units",
    },
}

_ELEMENT_TAGS = (
    f"{{{NS_SSD}}}System",
    f"{{{NS_SSD}}}Component",
    f"{{{NS_SSD}}}SignalDictionaryReference",
)


@dataclass
class MetaDataRef:
    """A ``ssc:MetaData`` node found on a carrier."""

    node: etree._Element
    kind: str | None
    mime: str | None
    source: str | None

    @property
    def inline_content(self) -> etree._Element | None:
        for child in self.node:
            if child.tag == Q_CONTENT:
                for payload in child:
                    if isinstance(payload.tag, str):
                        return payload
        return None


class _XmlHost:
    """Common behavior for SSD and SSV documents held as raw lxml trees."""

    root_tag: str = ""

    def __init__(self, entry: str, data: bytes):
        self.entry = entry
        parser = etree.XMLParser(remove_blank_text=False, remove_comments=False)
        try:
            self.tree = etree.fromstring(data, parser=parser).getroottree()
        except etree.XMLSyntaxError as exc:  # pragma: no cover - defensive
            raise PackageError(f"{entry}: not well-formed XML: {exc}") from exc
        self.root = self.tree.getroot()
        if self.root.tag != self.root_tag:
            raise PackageError(
                f"{entry}: unexpected root element {self.root.tag}, "
                f"expected {self.root_tag}"
            )

    # -- serialization ----------------------------------------------------

    def to_bytes(self) -> bytes:
        return etree.tostring(
            self.tree, xml_declaration=True, encoding="UTF-8", pretty_print=False
        )

    # -- version stamping -------------------------------------------------

    def stamp_version(self) -> None:
        """Set the host document version to 2.0 (MetaData is a 2.0 feature)."""
        if self.root.get("version") != SSP_VERSION:
            self.root.set("version", SSP_VERSION)

    # -- MetaData access --------------------------------------------------

    @staticmethod
    def metadata_of(carrier: etree._Element) -> list[MetaDataRef]:
        return [
            MetaDataRef(
                node=child,
                kind=child.get("kind"),
                mime=child.get("type"),
                source=child.get("source"),
            )
            for child in carrier
            if child.tag == Q_METADATA
        ]

    def inject_metadata(
        self,
        carrier: etree._Element,
        preds_key: CarrierKind,
        *,
        source: str,
        mime: str,
        kind: str,
    ) -> etree._Element:
        node = etree.SubElement(carrier, Q_METADATA)
        carrier.remove(node)  # re-insert at the right position below
        node.set("kind", kind)
        node.set("type", mime)
        node.set("source", source)
        idx = self._insertion_index(carrier, _PREDS[preds_key])
        self._insert_pretty(carrier, node, idx)
        self.stamp_version()
        return node

    def remove_metadata(self, ref: MetaDataRef) -> None:
        carrier = ref.node.getparent()
        if carrier is None:  # pragma: no cover - defensive
            raise AnchorError("MetaData node is detached")
        prev = ref.node.getprevious()
        is_last = ref.node.getnext() is None
        tail = ref.node.tail
        carrier.remove(ref.node)
        if is_last:
            if prev is not None:
                prev.tail = tail
            elif len(carrier) == 0:
                carrier.text = None

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _insertion_index(carrier: etree._Element, preds: set[str]) -> int:
        idx = 0
        for i, child in enumerate(carrier):
            if isinstance(child.tag, str) and (
                child.tag in preds or child.tag == Q_METADATA
            ):
                idx = i + 1
        return idx

    @staticmethod
    def _line_indent(el: etree._Element) -> str:
        """Whitespace that precedes ``el`` on its own line, best effort."""
        prev = el.getprevious()
        raw = (
            prev.tail
            if prev is not None
            else (el.getparent().text if el.getparent() is not None else None)
        )
        if raw and "\n" in raw:
            return raw.rsplit("\n", 1)[1]
        return ""

    def _insert_pretty(
        self, carrier: etree._Element, node: etree._Element, idx: int
    ) -> None:
        n = len(carrier)
        if n == 0:
            base = self._line_indent(carrier)
            carrier.text = "\n" + base + "  "
            node.tail = "\n" + base
            carrier.insert(0, node)
            return
        if idx >= n:  # append after last child
            last = carrier[-1]
            node.tail = last.tail
            last.tail = (
                carrier.text
                if (carrier.text and "\n" in carrier.text)
                else "\n" + self._line_indent(carrier) + "  "
            )
            carrier.append(node)
            return
        # insert before the child currently at idx: reuse its leading whitespace
        lead = carrier[idx - 1].tail if idx > 0 else carrier.text
        node.tail = lead
        carrier.insert(idx, node)


@dataclass(frozen=True)
class DefaultExperiment:
    """The SSD root's optional ``DefaultExperiment`` element.

    Either attribute may be absent even when the element is present (both
    are ``use="optional"`` in the schema); ``None`` on a field means the
    attribute was not written, not that it defaults to zero.
    """

    start_time: float | None
    stop_time: float | None


class SsdDocument(_XmlHost):
    """A ``*.ssd`` System Structure Description held as an lxml tree."""

    root_tag = f"{{{NS_SSD}}}SystemStructureDescription"

    # -- structure navigation ---------------------------------------------

    @property
    def root_system(self) -> etree._Element:
        for child in self.root:
            if child.tag == f"{{{NS_SSD}}}System":
                return child
        raise PackageError(f"{self.entry}: SSD has no root System element")

    @property
    def system_name(self) -> str:
        """The root system's ``name`` attribute (``""`` if absent)."""
        return self.root_system.get("name", "")

    @property
    def default_experiment(self) -> DefaultExperiment | None:
        """The root ``DefaultExperiment`` element, or ``None`` if absent.

        ``startTime``/``stopTime`` are parsed strictly: a value that is
        present but not a valid ``xs:double`` raises :class:`PackageError`
        rather than being silently dropped.
        """
        tag = f"{{{NS_SSD}}}DefaultExperiment"
        el = next((child for child in self.root if child.tag == tag), None)
        if el is None:
            return None
        return DefaultExperiment(
            start_time=self._parse_time(el, "startTime"),
            stop_time=self._parse_time(el, "stopTime"),
        )

    def _parse_time(self, el: etree._Element, attr: str) -> float | None:
        raw = el.get(attr)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError as exc:
            raise PackageError(
                f"{self.entry}: DefaultExperiment/@{attr}={raw!r} is not a "
                "valid xs:double"
            ) from exc

    @staticmethod
    def child_elements(el: etree._Element) -> list[tuple[str, etree._Element]]:
        """Named model elements below ``el`` (via its ``Elements`` child)."""
        out: list[tuple[str, etree._Element]] = []
        for wrap in el:
            if wrap.tag == f"{{{NS_SSD}}}Elements":
                for child in wrap:
                    if child.tag in _ELEMENT_TAGS:
                        out.append((child.get("name", ""), child))
        return out

    def element_at(self, path: tuple[str, ...]) -> etree._Element:
        """Resolve an exact path of element names below the root system."""
        el = self.root_system
        for i, name in enumerate(path):
            for cname, child in self.child_elements(el):
                if cname == name:
                    el = child
                    break
            else:
                raise AnchorError(
                    f"{self.entry}: no element {name!r} under "
                    f"{'/'.join(path[:i]) or '<root system>'}"
                )
        return el

    def resolve_dotted(self, dotted: str) -> list[tuple[str, ...]]:
        """All element paths that a dotted name may denote (name punning)."""
        results: list[tuple[str, ...]] = []

        def rec(el: etree._Element, rem: str, acc: tuple[str, ...]) -> None:
            for name, child in self.child_elements(el):
                if not name:
                    continue
                if rem == name:
                    results.append(acc + (name,))
                elif rem.startswith(name + "."):
                    rec(child, rem[len(name) + 1 :], acc + (name,))

        rec(self.root_system, dotted, ())
        return results

    def path_from_dotted(self, dotted: str) -> tuple[str, ...]:
        matches = self.resolve_dotted(dotted)
        if not matches:
            raise AnchorError(f"{self.entry}: no element matches path {dotted!r}")
        if len(matches) > 1:
            raise AmbiguousPathError(dotted, matches)
        return matches[0]

    @staticmethod
    def connector_names(el: etree._Element) -> set[str]:
        names: set[str] = set()
        for wrap in el:
            if wrap.tag == f"{{{NS_SSD}}}Connectors":
                for con in wrap:
                    if con.tag == f"{{{NS_SSD}}}Connector" and con.get("name"):
                        names.add(con.get("name"))
        return names

    def parameter_bindings(self, el: etree._Element) -> list[etree._Element]:
        out: list[etree._Element] = []
        for wrap in el:
            if wrap.tag == f"{{{NS_SSD}}}ParameterBindings":
                for b in wrap:
                    if b.tag == f"{{{NS_SSD}}}ParameterBinding":
                        out.append(b)
        return out

    def iter_carriers(
        self,
    ) -> Iterable[tuple[CarrierKind, CarrierPath, etree._Element]]:
        """Yield ``(kind, path_info, element)`` for every MetaData carrier."""
        yield ("ssd_root", None, self.root)

        def walk(el: etree._Element, path: tuple[str, ...]):
            yield ("element", path, el)
            for i, b in enumerate(self.parameter_bindings(el)):
                yield ("binding", (path, i), b)
            for name, child in self.child_elements(el):
                yield from walk(child, path + (name,))

        yield from walk(self.root_system, ())

    # -- variable name resolution (validation level 3) ---------------------

    def resolve_variable(self, scope: etree._Element, dotted: str) -> Verdict:
        """Classify a variable name relative to ``scope``.

        Returns ``"resolved"`` (a declared connector matches), ``"unknown"``
        (the name lands on a Component that may define it internally, e.g.
        an FMU variable not exposed as a connector) or ``"bad"`` (no
        interpretation reaches a plausible variable).
        """
        outcomes: set[str] = set()

        def rec(el: etree._Element, rem: str) -> None:
            if rem in self.connector_names(el):
                outcomes.add("resolved")
                return
            descended = False
            for name, child in self.child_elements(el):
                if name and rem.startswith(name + "."):
                    descended = True
                    rec(child, rem[len(name) + 1 :])
            if not descended:
                if el.tag == f"{{{NS_SSD}}}Component":
                    # FMI variable names may themselves contain dots.
                    outcomes.add("unknown")
                else:
                    outcomes.add("bad")

        rec(scope, dotted)
        for verdict in ("resolved", "unknown", "bad"):
            if verdict in outcomes:
                return verdict
        return "bad"


class SsvDocument(_XmlHost):
    """A ``*.ssv`` parameter set held as an lxml tree."""

    root_tag = f"{{{NS_SSV}}}ParameterSet"

    def parameter_names(self) -> set[str]:
        names: set[str] = set()
        for wrap in self.root:
            if wrap.tag == f"{{{NS_SSV}}}Parameters":
                for p in wrap:
                    if p.tag == f"{{{NS_SSV}}}Parameter" and p.get("name"):
                        names.add(p.get("name"))
        return names
