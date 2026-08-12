"""SSP package I/O and the high-level uq facade.

The archive is loaded as an ordered map of ``entry name -> bytes``. Host
documents (SSD, SSV) are parsed lazily into lxml trees and re-serialized
only when omuq-python modified them. All other entries are written back
unchanged on :meth:`SspPackage.save`.
"""

from __future__ import annotations

import os
import posixpath
import re
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING

from ._xml import parse_study, serialize_study, stamp_generation_info
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
    UQ_SUFFIX,
)
from .errors import (
    AnchorError,
    DuplicateStudyError,
    LinkError,
    ModelError,
    PackageError,
)
from .model import (
    Activity,
    Domain,
    UncertaintyQuantification,
    activities_of,
    domains_of,
)
from .validation import ValidationReport, validate_package
from .xmlhost import MetaDataRef, SsdDocument, SsvDocument

if TYPE_CHECKING:
    # Annotation-only: the results write-back and the simulation layer are
    # imported inside the methods that use them (see UqManager.update /
    # record_result), so opening a package never pulls in a simulator.
    from .simulation import Sample, SimulationResult
    from .writeback import RecordedResult

ROOT_SSD = "SystemStructure.ssd"


def _entry_slug(base: str) -> str:
    """The file-name stem omuq derives from a study name or file name.

    Shared by :meth:`UqManager._new_entry_name` and the results write-back
    (:mod:`omuq.writeback`), so a study's document and its result tables
    are named by the same rule. The recommended ``.uq.xml`` suffix is
    stripped so that re-slugging an existing entry name is idempotent.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") or "study"
    if slug.endswith(UQ_SUFFIX):
        slug = slug[: -len(UQ_SUFFIX)]
    return slug


@dataclass
class AttachedStudy:
    """A study found in (or just attached to) a package."""

    anchor: Anchor
    entry: str | None  # archive path of the omuq document (None if inline)
    source: str | None  # the raw MetaData/@source attribute value
    kind: str | None
    mime: str | None
    document: UncertaintyQuantification

    @property
    def name(self) -> str:
        """The study's name (a convenience alias for ``document.name``)."""
        return self.document.name

    @property
    def activities(self) -> list[Activity]:
        """The study's activities, via :func:`omuq.model.activities_of`."""
        return activities_of(self.document)

    @property
    def domains(self) -> list[Domain]:
        """The study's domains, via :func:`omuq.model.domains_of`."""
        return domains_of(self.document)


class SspPackage:
    """An SSP archive opened for omuq inspection and editing."""

    def __init__(self, entries: dict[str, bytes]):
        if ROOT_SSD not in entries:
            raise PackageError(
                "not a valid SSP: missing mandatory root entry "
                f"{ROOT_SSD!r} (SSP 2.0, chapter 3)"
            )
        self._entries: dict[str, bytes] = dict(entries)
        self._order: list[str] = list(entries)
        self._hosts: dict[str, SsdDocument | SsvDocument] = {}
        self._dirty: set[str] = set()
        #: The filesystem path this package was opened from, if any. ``None``
        #: for packages opened from a file object (e.g. a ``BytesIO``) or
        #: built in memory, since there is no path to record.
        self.path: Path | None = None
        self.uq = UqManager(self)

    # -- construction ------------------------------------------------------

    @classmethod
    def open(cls, path: str | os.PathLike[str] | IO[bytes]) -> SspPackage:
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                entries = {n: zf.read(n) for n in names if not n.endswith("/")}
        except (OSError, zipfile.BadZipFile) as exc:
            raise PackageError(f"cannot open SSP archive {path!r}: {exc}") from exc
        pkg = cls(entries)
        if isinstance(path, (str, os.PathLike)):
            pkg.path = Path(path)
        return pkg

    def save(self, path: str | os.PathLike[str] | IO[bytes]) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in self._order:
                if name not in self._entries:
                    continue  # deleted
                zf.writestr(name, self._payload(name))

    # -- entry access ------------------------------------------------------

    def entry_names(self) -> list[str]:
        return [n for n in self._order if n in self._entries]

    def has_entry(self, name: str) -> bool:
        return name in self._entries

    def read(self, name: str) -> bytes:
        """Current bytes of an entry, including unsaved host edits."""
        if name not in self._entries:
            raise PackageError(f"no such entry: {name!r}")
        return self._payload(name)

    def _payload(self, name: str) -> bytes:
        if name in self._dirty and name in self._hosts:
            return self._hosts[name].to_bytes()
        return self._entries[name]

    def add_entry(self, name: str, data: bytes) -> None:
        if name in self._entries:
            raise PackageError(f"entry already exists: {name!r}")
        self._entries[name] = data
        self._order.append(name)

    def remove_entry(self, name: str) -> None:
        self._entries.pop(name, None)
        self._hosts.pop(name, None)
        self._dirty.discard(name)

    def replace_entry(self, name: str, data: bytes) -> None:
        """Overwrite an existing non-host entry in place.

        Unlike ``remove_entry`` + ``add_entry``, the entry keeps its
        position in :meth:`entry_names`. SSD/SSV entries are host documents
        (see the module docstring) and must be edited through
        :meth:`ssd`/:meth:`ssv` instead, whether or not they have been
        parsed as a host yet.
        """
        if name not in self._entries:
            raise PackageError(f"no such entry: {name!r}")
        if (
            name in self._hosts
            or name in self.ssd_entries()
            or name in self.ssv_entries()
        ):
            raise PackageError(
                f"{name!r} is a host document (.ssd/.ssv); edit it through "
                "pkg.ssd()/pkg.ssv() instead of replace_entry()"
            )
        self._entries[name] = data

    # -- host documents ----------------------------------------------------

    def ssd_entries(self) -> list[str]:
        return [
            n for n in self.entry_names() if "/" not in n and n.lower().endswith(".ssd")
        ]

    def ssv_entries(self) -> list[str]:
        return [n for n in self.entry_names() if n.lower().endswith(".ssv")]

    def ssd(self, name: str = ROOT_SSD) -> SsdDocument:
        return self._host(name, SsdDocument)

    def ssv(self, name: str) -> SsvDocument:
        return self._host(name, SsvDocument)

    def _host(self, name, cls):
        host = self._hosts.get(name)
        if host is None:
            if name not in self._entries:
                raise PackageError(f"no such entry: {name!r}")
            host = cls(name, self._entries[name])
            self._hosts[name] = host
        if not isinstance(host, cls):  # pragma: no cover - defensive
            raise PackageError(f"{name!r} already parsed as {type(host).__name__}")
        return host

    def _mark_dirty(self, name: str) -> None:
        self._dirty.add(name)


class UqManager:
    """The omuq-specific operations on a package."""

    def __init__(self, pkg: SspPackage):
        self._pkg = pkg

    # -- reading -----------------------------------------------------------

    def studies(self) -> list[AttachedStudy]:
        out: list[AttachedStudy] = []
        for anchor, host, ref in self._iter_omuq_metadata():
            document, entry = self._load(host, ref)
            out.append(
                AttachedStudy(
                    anchor=anchor,
                    entry=entry,
                    source=ref.source,
                    kind=ref.kind,
                    mime=ref.mime,
                    document=document,
                )
            )
        return out

    def study(self, key: int | str = 0) -> AttachedStudy:
        """One attached study, by position in :meth:`studies` or by name.

        Raises :class:`~omuq.errors.PackageError` when the package has no
        such study, listing the names that are actually attached.
        """
        studies = self.studies()
        if isinstance(key, str):
            for s in studies:
                if s.document.name == key:
                    return s
            known = ", ".join(repr(s.document.name) for s in studies) or "none"
            raise PackageError(
                f"no study named {key!r} is attached to this package "
                f"(attached: {known})"
            )
        try:
            return studies[key]
        except IndexError:
            raise PackageError(
                f"no study at index {key}; the package has {len(studies)} attached"
            ) from None

    def _iter_omuq_metadata(
        self,
    ) -> Iterable[tuple[Anchor, SsdDocument | SsvDocument, MetaDataRef]]:
        pkg = self._pkg
        for ssd_name in pkg.ssd_entries():
            host = pkg.ssd(ssd_name)
            for kind, info, el in host.iter_carriers():
                for ref in host.metadata_of(el):
                    if ref.mime not in MIME_ALIASES:
                        continue
                    if kind == "ssd_root":
                        anchor: Anchor = SsdRootAnchor(ssd_name)
                    elif kind == "element":
                        anchor = ElementAnchor(info, ssd_name)
                    else:
                        path, idx = info
                        anchor = ParameterBindingAnchor(path, idx, ssd_name)
                    yield anchor, host, ref
        for ssv_name in pkg.ssv_entries():
            host = pkg.ssv(ssv_name)
            for ref in host.metadata_of(host.root):
                if ref.mime in MIME_ALIASES:
                    yield SsvAnchor(ssv_name), host, ref

    def _load(self, host, ref: MetaDataRef):
        if ref.source is not None:
            entry = self.resolve_source(host.entry, ref.source)
            try:
                data = self._pkg.read(entry)
            except PackageError as exc:
                raise LinkError(
                    f"{host.entry}: MetaData source {ref.source!r} does not "
                    f"resolve to a package entry ({entry})"
                ) from exc
            return self._parsed(data, entry), entry
        inline = ref.inline_content
        if inline is None:
            raise LinkError(
                f"{host.entry}: omuq MetaData has neither source nor Content"
            )
        from lxml import etree

        where = f"{host.entry} (inline MetaData/Content)"
        return self._parsed(etree.tostring(inline), where), None

    @staticmethod
    def _parsed(data: bytes, where: str) -> UncertaintyQuantification:
        """``parse_study(data)``, with any parse failure wrapped as `LinkError`.

        xsdata raises ``xsdata.exceptions.ParserError`` (a ``ValueError``
        subclass) for corrupted or non-omuq bytes, and the generated
        dataclass ``__init__`` raises a bare ``TypeError`` for well-formed
        XML missing a required attribute. Both are third-party
        implementation details, so both are caught here and re-raised as
        `LinkError`, naming what failed to parse.
        """
        try:
            return parse_study(data)
        except (ValueError, TypeError) as exc:
            raise LinkError(
                f"{where}: not a parseable omuq document ({exc}); the "
                "entry's content is not valid UncertaintyQuantification XML "
                "(corrupted bytes, or a schema mismatch)"
            ) from exc

    @staticmethod
    def resolve_source(host_entry: str, source: str) -> str:
        if "://" in source:
            raise LinkError(f"absolute URI sources are not supported: {source!r}")
        base = posixpath.dirname(host_entry)
        resolved = posixpath.normpath(posixpath.join(base, source))
        if resolved.startswith(".."):
            raise LinkError(
                f"source {source!r} escapes the package (resolves to {resolved})"
            )
        return resolved

    # -- attaching ---------------------------------------------------------

    def attach(
        self,
        document: UncertaintyQuantification,
        anchor: Anchor,
        *,
        filename: str | None = None,
        kind: str = DEFAULT_KIND,
        mime: str = MIME_OMUQ,
    ) -> AttachedStudy:
        if not document.name:
            raise ModelError("study must have a name (required by the schema)")
        if document.name in self._attached_names():
            raise DuplicateStudyError(
                f"a study named {document.name!r} is already attached; "
                "study names must be unique per package"
            )

        host, carrier, preds_key = self._resolve_anchor(anchor)

        entry = self._new_entry_name(filename or document.name)
        stamp_generation_info(document)
        self._pkg.add_entry(entry, serialize_study(document))

        source = posixpath.relpath(entry, posixpath.dirname(host.entry) or ".")
        host.inject_metadata(carrier, preds_key, source=source, mime=mime, kind=kind)
        self._pkg._mark_dirty(host.entry)
        return AttachedStudy(
            anchor=anchor,
            entry=entry,
            source=source,
            kind=kind,
            mime=mime,
            document=document,
        )

    def detach(self, attached: AttachedStudy) -> None:
        """Remove a study link and garbage-collect its document if unreferenced."""
        host, carrier, _ = self._resolve_anchor(attached.anchor)
        for ref in host.metadata_of(carrier):
            if ref.mime in MIME_ALIASES and ref.source == attached.source:
                host.remove_metadata(ref)
                self._pkg._mark_dirty(host.entry)
                break
        else:
            raise AnchorError(
                f"no omuq MetaData with source {attached.source!r} on this anchor"
            )
        if attached.entry is not None and self._refcount(attached.entry) == 0:
            self._pkg.remove_entry(attached.entry)

    def _refcount(self, entry: str) -> int:
        count = 0
        for _anchor, host, ref in self._iter_omuq_metadata():
            if ref.source is None:
                continue
            try:
                if self.resolve_source(host.entry, ref.source) == entry:
                    count += 1
            except LinkError:
                continue
        return count

    def _attached_entries(self) -> frozenset[str]:
        """The package entry of every attached (file-backed) study.

        Used by :meth:`record_result` for the target check in
        :mod:`omuq.writeback`'s ``_csv_entry_name``. Resolves each
        MetaData's ``source`` the same way :meth:`_refcount` does, without
        parsing the omuq documents themselves (unlike :meth:`studies`), so
        a broken link elsewhere in the package does not block recording
        into an unrelated study.
        """
        entries: set[str] = set()
        for _anchor, host, ref in self._iter_omuq_metadata():
            if ref.source is None:
                continue
            try:
                entries.add(self.resolve_source(host.entry, ref.source))
            except LinkError:
                continue
        return frozenset(entries)

    # -- writing back ------------------------------------------------------

    def update(self, attached: AttachedStudy) -> None:
        """Write an edited study document back into its package entry.

        Changes made to a document from :meth:`studies` stay in memory
        until this method re-serializes it. The document's
        ``generationDateAndTime`` is refreshed (guideline section 4.5 asks
        writers to fill the top-level metadata when modifying a document);
        ``generationTool`` is only filled in when absent.

        Raises :class:`~omuq.errors.LinkError` for a study that is stored
        as inline ``ssc:MetaData/Content``: it has no entry of its own to
        replace, and omuq-python does not rewrite third-party host
        documents around inline content.
        """
        from . import writeback

        writeback.update_study(self._pkg, attached)

    def record_result(
        self,
        attached: AttachedStudy,
        result: SimulationResult,
        *,
        activity: int | str | Activity = 0,
        samples: Sequence[Sample] | None = None,
        store_samples: bool | str = True,
        summaries: bool | str = "auto",
        update: bool = True,
    ) -> RecordedResult:
        """Record a finished run into one activity's ``ResultSet``.

        Writes the run's domain-excursion counts and sample count as
        ``ErrorMetric`` results; with ``samples`` (typically an
        :class:`~omuq.simulation.MemorySink`'s ``.samples``) it also stores
        the sample table as a checksummed CSV entry under ``resources/uq/``
        and, when ``summaries`` says so, a ``Normal(mu, sigma)`` per observed
        variable.

        * ``activity`` - a position, an id or name, or the activity object,
          resolved like :meth:`omuq.simulation.Simulation.for_study`'s.
        * ``store_samples`` - ``False`` to keep the metrics only, or a file
          name to place the CSV under ``resources/uq/`` instead of the
          derived ``<study>-<activity>.results.csv``.
        * ``summaries`` - ``"auto"`` (only when the activity's
          ``DesiredResults`` asks for a mean or a standard deviation),
          ``True``, or ``False``.
        * ``update`` - ``False`` to leave the package entry untouched and
          call :meth:`update` later.

        The activity's ``ResultSet`` is replaced, not appended to: omuq's
        ``Results`` elements carry no identity, so replacing the whole set
        is what keeps recording idempotent. See :mod:`omuq.writeback`.
        """
        from . import writeback

        return writeback.record_result(
            self._pkg,
            attached,
            result,
            activity=activity,
            samples=samples,
            store_samples=store_samples,
            summaries=summaries,
            update=update,
            attached_entries=self._attached_entries(),
        )

    # -- validation --------------------------------------------------------

    def validate(self, level: int = 3) -> ValidationReport:
        return validate_package(self._pkg, level=level)

    # -- helpers -----------------------------------------------------------

    def _attached_names(self) -> set[str]:
        """The ``name`` of every linked document, without fully parsing it.

        Used by :meth:`attach` for the duplicate-name check instead of
        :meth:`studies`: only the root ``name`` attribute is needed, and a
        single unresolvable or malformed link would make :meth:`studies`
        raise and block attaching an unrelated study. Broken links are
        skipped here; :meth:`validate` reports them.
        """
        from lxml import etree

        names: set[str] = set()
        for _anchor, host, ref in self._iter_omuq_metadata():
            if ref.source is not None:
                try:
                    entry = self.resolve_source(host.entry, ref.source)
                    root_name = etree.fromstring(self._pkg.read(entry)).get("name")
                except (LinkError, PackageError, etree.XMLSyntaxError):
                    continue
            else:
                inline = ref.inline_content
                root_name = inline.get("name") if inline is not None else None
            if root_name:
                names.add(root_name)
        return names

    def _resolve_anchor(self, anchor: Anchor):
        pkg = self._pkg
        if isinstance(anchor, SsdRootAnchor):
            host = pkg.ssd(anchor.ssd_name)
            return host, host.root, "ssd_root"
        if isinstance(anchor, ElementAnchor):
            host = pkg.ssd(anchor.ssd_name)
            return host, host.element_at(anchor.path), "element"
        if isinstance(anchor, ParameterBindingAnchor):
            host = pkg.ssd(anchor.ssd_name)
            el = host.element_at(anchor.path)
            bindings = host.parameter_bindings(el)
            if not 0 <= anchor.index < len(bindings):
                raise AnchorError(
                    f"element {'/'.join(anchor.path) or '<root system>'} has "
                    f"{len(bindings)} parameter binding(s); index "
                    f"{anchor.index} is out of range"
                )
            return host, bindings[anchor.index], "binding"
        if isinstance(anchor, SsvAnchor):
            host = pkg.ssv(anchor.entry)
            return host, host.root, "ssv_root"
        raise AnchorError(f"unsupported anchor type {type(anchor).__name__}")

    def _new_entry_name(self, base: str) -> str:
        slug = _entry_slug(base)
        candidate = f"{UQ_RESOURCE_DIR}/{slug}{UQ_SUFFIX}"
        n = 1
        while self._pkg.has_entry(candidate):
            n += 1
            candidate = f"{UQ_RESOURCE_DIR}/{slug}-{n}{UQ_SUFFIX}"
        return candidate
