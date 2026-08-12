"""Phase 2: package/SSD metadata.

Covers ``SsdDocument.system_name``/``default_experiment``, the
``SspPackage.has_entry``/``replace_entry`` write-back primitives,
``UqManager.study()``, ``attach()``'s robustness against a pre-existing
broken link, and the ``AttachedStudy`` convenience properties.
"""

import pytest
from conftest import make_study, reopen

from omuq import (
    DuplicateStudyError,
    ElementAnchor,
    PackageError,
    SsdRootAnchor,
    SspPackage,
    model,
)
from omuq.constants import MIME_OMUQ
from omuq.xmlhost import DefaultExperiment, SsdDocument

NO_DEFAULT_EXPERIMENT = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    version="2.0" name="NoExperiment">
  <ssd:System name="plant"/>
</ssd:SystemStructureDescription>
"""

BAD_START_TIME = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    version="2.0" name="BadTime">
  <ssd:System name="plant"/>
  <ssd:DefaultExperiment startTime="not-a-number" stopTime="1.0"/>
</ssd:SystemStructureDescription>
"""

NO_SYSTEM_NAME = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    version="2.0" name="NoSystemName">
  <ssd:System/>
</ssd:SystemStructureDescription>
"""


# -- SsdDocument.system_name -------------------------------------------------


def test_system_name_reads_the_root_system_name(pkg):
    assert pkg.ssd().system_name == "plant"


def test_system_name_is_empty_when_the_attribute_is_absent():
    host = SsdDocument("x.ssd", NO_SYSTEM_NAME.encode())
    assert host.system_name == ""


# -- SsdDocument.default_experiment ------------------------------------------


def test_default_experiment_reads_start_and_stop_time(pkg):
    assert pkg.ssd().default_experiment == DefaultExperiment(
        start_time=0.0, stop_time=1.0
    )


def test_default_experiment_is_none_when_the_element_is_absent():
    host = SsdDocument("x.ssd", NO_DEFAULT_EXPERIMENT.encode())
    assert host.default_experiment is None


def test_default_experiment_unparsable_start_time_raises():
    host = SsdDocument("x.ssd", BAD_START_TIME.encode())
    with pytest.raises(PackageError, match="startTime"):
        _ = host.default_experiment


# -- SspPackage.has_entry / replace_entry ------------------------------------


def test_has_entry(pkg):
    assert pkg.has_entry("SystemStructure.ssd") is True
    assert pkg.has_entry("no/such/entry.txt") is False


def test_replace_entry_happy_path(pkg):
    pkg.replace_entry("resources/battery.fmu", b"new fmu bytes")
    assert pkg.read("resources/battery.fmu") == b"new fmu bytes"
    pkg2, _ = reopen(pkg)
    assert pkg2.read("resources/battery.fmu") == b"new fmu bytes"


def test_replace_entry_missing_entry_raises(pkg):
    with pytest.raises(PackageError, match="no such entry"):
        pkg.replace_entry("no/such/entry.txt", b"x")


def test_replace_entry_rejects_ssd_host_entry(pkg):
    with pytest.raises(PackageError, match="host"):
        pkg.replace_entry("SystemStructure.ssd", b"<x/>")


def test_replace_entry_rejects_ssv_host_entry(pkg):
    with pytest.raises(PackageError, match="host"):
        pkg.replace_entry("resources/params.ssv", b"<x/>")


def test_replace_entry_preserves_archive_order(pkg):
    before = pkg.entry_names()
    pkg.replace_entry("resources/battery.fmu", b"different bytes now")
    assert pkg.entry_names() == before


# -- UqManager.study() --------------------------------------------------------


def test_study_by_index_and_name(pkg):
    pkg.uq.attach(make_study("A"), SsdRootAnchor())
    pkg.uq.attach(
        make_study("B", param="R0", observed=("V",)), ElementAnchor(("battery",))
    )
    assert pkg.uq.study().document.name == "A"  # default key=0
    assert pkg.uq.study(0).document.name == "A"
    assert pkg.uq.study(1).document.name == "B"
    assert pkg.uq.study("A").document.name == "A"
    assert pkg.uq.study("B").document.name == "B"


def test_study_unknown_name_lists_available_names(pkg):
    pkg.uq.attach(make_study("A"), SsdRootAnchor())
    with pytest.raises(PackageError, match="A"):
        pkg.uq.study("NoSuchStudy")


def test_study_index_out_of_range_raises(pkg):
    pkg.uq.attach(make_study("A"), SsdRootAnchor())
    with pytest.raises(PackageError):
        pkg.uq.study(5)


def test_study_on_empty_package_raises(pkg):
    with pytest.raises(PackageError):
        pkg.uq.study()


# -- attach() robustness against a pre-existing broken link ------------------


def test_attach_survives_a_pre_existing_broken_link(pkg):
    host = pkg.ssd()
    host.inject_metadata(
        host.root,
        "ssd_root",
        source="resources/uq/missing.uq.xml",  # never added to the package
        mime=MIME_OMUQ,
        kind="quality",
    )
    pkg._mark_dirty(host.entry)

    # Before the fix, this raised LinkError because attach()'s duplicate
    # check called studies(), which fails on the dangling MetaData source.
    attached = pkg.uq.attach(make_study("NewStudy"), ElementAnchor(("battery",)))
    assert attached.document.name == "NewStudy"

    report = pkg.uq.validate(level=2)
    assert not report.ok
    assert any(i.code == "L2.link" for i in report.errors)


def test_duplicate_check_still_works_and_ignores_broken_links(pkg):
    pkg.uq.attach(make_study("A"), SsdRootAnchor())
    host = pkg.ssd()
    host.inject_metadata(
        host.root,
        "ssd_root",
        source="resources/uq/missing.uq.xml",
        mime=MIME_OMUQ,
        kind="quality",
    )
    pkg._mark_dirty(host.entry)
    with pytest.raises(DuplicateStudyError):
        pkg.uq.attach(make_study("A"), ElementAnchor(("battery",)))


# -- AttachedStudy properties -------------------------------------------------


def test_attached_study_properties(pkg):
    attached = pkg.uq.attach(make_study(), SsdRootAnchor())
    assert attached.name == attached.document.name == "BatteryUQ"
    assert attached.activities == model.activities_of(attached.document)
    assert attached.domains == model.domains_of(attached.document)


# -- SspPackage.path -----------------------------------------------------


def test_open_from_a_filesystem_path_records_path(tmp_path, ssp_bytes):
    p = tmp_path / "demo.ssp"
    p.write_bytes(ssp_bytes)
    pkg = SspPackage.open(p)
    assert pkg.path == p


def test_open_from_a_string_path_records_path(tmp_path, ssp_bytes):
    p = tmp_path / "demo.ssp"
    p.write_bytes(ssp_bytes)
    pkg = SspPackage.open(str(p))
    assert pkg.path == p


def test_open_from_a_file_object_leaves_path_none(pkg):
    assert pkg.path is None
