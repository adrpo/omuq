import io
import zipfile

import pytest
from conftest import EXTRA, FMU, make_study, reopen
from lxml import etree

from omuq import (
    DuplicateStudyError,
    ElementAnchor,
    PackageError,
    ParameterBindingAnchor,
    SsdRootAnchor,
    SspPackage,
    SsvAnchor,
)
from omuq.constants import MIME_OMUQ, NS_SSC, NS_SSD

Q_MD = f"{{{NS_SSC}}}MetaData"


def test_open_requires_root_ssd():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no ssd here")
    buf.seek(0)
    with pytest.raises(PackageError, match="SystemStructure.ssd"):
        SspPackage.open(buf)


def test_attach_read_export_reimport_at_root(pkg):
    study = make_study()
    attached = pkg.uq.attach(study, SsdRootAnchor())
    assert attached.entry == "resources/uq/BatteryUQ.uq.xml"
    assert attached.source == "resources/uq/BatteryUQ.uq.xml"

    pkg2, _ = reopen(pkg)
    studies = pkg2.uq.studies()
    assert len(studies) == 1
    got = studies[0]
    assert got.anchor == SsdRootAnchor("SystemStructure.ssd")
    assert got.mime == MIME_OMUQ
    assert got.kind == "quality"
    # the parsed document equals the document that was attached
    assert got.document == attached.document
    assert got.document.generation_tool.startswith("omuq-python")


def test_untouched_entries_are_byte_identical(pkg, ssp_bytes):
    pkg.uq.attach(make_study(), SsdRootAnchor())
    _, out_bytes = reopen(pkg)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        assert zf.read("extra/com.vendor.tool/notes.txt") == EXTRA
        assert zf.read("resources/battery.fmu") == FMU
        # untouched SSV entry stays byte-identical to the input archive
        with zipfile.ZipFile(io.BytesIO(ssp_bytes)) as zin:
            assert zf.read("resources/params.ssv") == zin.read("resources/params.ssv")


def test_host_edit_preserves_foreign_content_and_stamps_version(pkg):
    pkg.uq.attach(make_study(), SsdRootAnchor())
    out = pkg.read("SystemStructure.ssd").decode()
    assert "vendor comment that must survive" in out
    assert 'keep="me"' in out
    root = etree.fromstring(pkg.read("SystemStructure.ssd"))
    assert root.get("version") == "2.0"


def test_attach_at_component_orders_metadata_before_annotations(pkg):
    study = make_study(param="R0", observed=("V",))
    pkg.uq.attach(study, ElementAnchor(("battery",)))
    root = etree.fromstring(pkg.read("SystemStructure.ssd"))
    comp = root.find(f".//{{{NS_SSD}}}Component[@name='battery']")
    tags = [c.tag for c in comp if isinstance(c.tag, str)]
    md = tags.index(Q_MD)
    assert tags.index(f"{{{NS_SSD}}}Connectors") < md
    assert md < tags.index(f"{{{NS_SSD}}}Annotations")

    report = pkg.uq.validate(level=1)
    assert report.ok, str(report)


def test_attach_at_parameter_binding(pkg):
    study = make_study(param="battery.R0", observed=("battery.V",))
    attached = pkg.uq.attach(study, ParameterBindingAnchor(path=(), index=0))
    pkg2, _ = reopen(pkg)
    got = pkg2.uq.studies()
    assert len(got) == 1
    assert got[0].anchor == ParameterBindingAnchor((), 0, "SystemStructure.ssd")
    assert got[0].document == attached.document
    assert pkg2.uq.validate(level=1).ok


def test_attach_at_ssv_overlay(pkg):
    study = make_study(param="battery.R0", observed=())
    attached = pkg.uq.attach(study, SsvAnchor("resources/params.ssv"))
    # relative source from resources/params.ssv into resources/uq/
    assert attached.source == "uq/BatteryUQ.uq.xml"
    pkg2, _ = reopen(pkg)
    got = pkg2.uq.studies()
    assert got[0].anchor == SsvAnchor("resources/params.ssv")
    root = etree.fromstring(pkg2.read("resources/params.ssv"))
    assert root.get("version") == "2.0"
    assert pkg2.uq.validate(level=1).ok


def test_multiple_studies_and_unique_names(pkg):
    pkg.uq.attach(make_study("A"), SsdRootAnchor())
    pkg.uq.attach(
        make_study("B", param="R0", observed=("V",)), ElementAnchor(("battery",))
    )
    with pytest.raises(DuplicateStudyError):
        pkg.uq.attach(make_study("A"), SsdRootAnchor())
    pkg2, _ = reopen(pkg)
    assert {s.document.name for s in pkg2.uq.studies()} == {"A", "B"}
    assert pkg2.uq.validate(level=1).ok


def test_coexists_with_foreign_metadata(pkg):
    # a pre-existing SRMD MetaData node on the root must not be reported
    host = pkg.ssd()
    host.inject_metadata(
        host.root,
        "ssd_root",
        source="resources/other.srmd",
        mime="application/x-srmd-meta-data",
        kind="quality",
    )
    pkg._mark_dirty(host.entry)
    pkg.add_entry("resources/other.srmd", b"<x/>")
    pkg.uq.attach(make_study(), SsdRootAnchor())
    pkg2, _ = reopen(pkg)
    studies = pkg2.uq.studies()
    assert len(studies) == 1  # only the omuq study is returned
    root = etree.fromstring(pkg2.read("SystemStructure.ssd"))
    assert len(root.findall(Q_MD)) == 2  # both MetaData nodes are present


def test_detach_removes_link_and_garbage_collects(pkg):
    attached = pkg.uq.attach(make_study(), SsdRootAnchor())
    assert attached.entry in pkg.entry_names()
    pkg.uq.detach(attached)
    assert attached.entry not in pkg.entry_names()
    pkg2, _ = reopen(pkg)
    assert pkg2.uq.studies() == []


def test_detach_keeps_shared_resource(pkg):
    attached = pkg.uq.attach(make_study(), SsdRootAnchor())
    # second link to the same document from the battery component
    host = pkg.ssd()
    host.inject_metadata(
        host.element_at(("battery",)),
        "element",
        source=attached.source,
        mime=MIME_OMUQ,
        kind="quality",
    )
    pkg._mark_dirty(host.entry)
    pkg.uq.detach(attached)
    assert attached.entry in pkg.entry_names()  # still referenced once
    pkg2, _ = reopen(pkg)
    assert len(pkg2.uq.studies()) == 1


def test_reads_inline_content(pkg):
    from omuq import serialize_study

    payload = serialize_study(make_study("Inline"))
    inline_doc = etree.fromstring(payload)
    host = pkg.ssd()
    md = host.inject_metadata(
        host.root, "ssd_root", source="placeholder", mime=MIME_OMUQ, kind="quality"
    )
    del md.attrib["source"]
    content = etree.SubElement(md, f"{{{NS_SSC}}}Content")
    content.append(inline_doc)
    pkg._mark_dirty(host.entry)
    pkg2, _ = reopen(pkg)
    studies = pkg2.uq.studies()
    assert len(studies) == 1
    assert studies[0].entry is None
    assert studies[0].document.name == "Inline"


ROOT_WITH_ANNOTATIONS = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
    version="1.0" name="Annotated">
  <ssd:System name="plant">
    <ssd:Elements>
      <ssd:Component name="battery" source="resources/battery.fmu"/>
    </ssd:Elements>
  </ssd:System>
  <ssd:Annotations>
    <ssc:Annotation type="com.vendor.root"><data xmlns=""/></ssc:Annotation>
  </ssd:Annotations>
</ssd:SystemStructureDescription>
"""


def test_root_metadata_inserted_before_existing_annotations():
    import io as _io
    import zipfile as _zip

    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w") as zf:
        zf.writestr("SystemStructure.ssd", ROOT_WITH_ANNOTATIONS)
        zf.writestr("resources/battery.fmu", b"x")
    buf.seek(0)
    pkg = SspPackage.open(buf)
    pkg.uq.attach(make_study("Ann", param="battery.R0"), SsdRootAnchor())
    root = etree.fromstring(pkg.read("SystemStructure.ssd"))
    tags = [c.tag for c in root if isinstance(c.tag, str)]
    assert tags.index(Q_MD) < tags.index(f"{{{NS_SSD}}}Annotations")
    assert pkg.uq.validate(level=1).ok
