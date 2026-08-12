import hashlib

import pytest
from conftest import make_study

from omuq import AmbiguousPathError, ElementAnchor, SsdRootAnchor, SsvAnchor, model
from omuq.xmlhost import SsdDocument


def codes(report, level=None):
    issues = (
        report.issues
        if level is None
        else [i for i in report.issues if i.level == level]
    )
    return {i.code for i in issues}


def test_clean_package_validates(pkg):
    pkg.uq.attach(make_study(), SsdRootAnchor())
    report = pkg.uq.validate()
    assert report.ok, str(report)
    assert not report.warnings, str(report)


def test_l2_broken_reference(pkg):
    study = make_study("Broken")
    model.activity_of(study).activity_domain_ref = "no-such-domain"
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert "L2.broken-ref" in codes(report, "error")


def test_l2_reference_resolves_to_id(pkg):
    study = make_study("WithDomain")
    dom = model.TypedOperationalDomainType(
        id="dom1", kind=model.TypedOperationalDomainKind.MODELED_OPERATIONAL_DOMAIN
    )
    model.add_domain(study, dom)
    model.activity_of(study).activity_domain_ref = "dom1"
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert "L2.broken-ref" not in codes(report)


def test_l2_external_source_and_checksum(pkg):
    data = b"0.1 0.2\n0.3 0.4\n"
    pkg.add_entry("resources/uq/points.csv", data)

    study = make_study("Ext")
    params = model.activity_of(study).parameter_set.parameters
    params.source = "points.csv"
    params.checksum = hashlib.sha256(data).hexdigest()
    params.checksum_type = "sha-256"
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert "L2.missing-source" not in codes(report)
    assert "L2.checksum" not in codes(report)

    # now corrupt the checksum
    study2 = make_study("Ext2")
    params2 = model.activity_of(study2).parameter_set.parameters
    params2.source = "points.csv"
    params2.checksum = "deadbeef"
    params2.checksum_type = "sha-256"
    pkg.uq.attach(study2, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert "L2.checksum" in codes(report, "error")


def test_l2_missing_external_source(pkg):
    study = make_study("Missing")
    model.activity_of(study).parameter_set.parameters.source = "nope.csv"
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate(level=2)
    assert "L2.missing-source" in codes(report, "error")


def test_l3_names_resolve_at_root_anchor(pkg):
    pkg.uq.attach(make_study(), SsdRootAnchor())  # battery.R0, battery.V
    report = pkg.uq.validate()
    assert report.ok and not report.warnings, str(report)


def test_l3_undeclared_component_variable_is_warning(pkg):
    study = make_study("Warn", param="battery.R_internal", observed=("battery.V",))
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate()
    assert "L3.undeclared-variable" in codes(report, "warning")
    assert report.ok  # warnings only


def test_l3_bad_path_is_error(pkg):
    study = make_study("Bad", param="nosuch.R0", observed=("battery.V",))
    pkg.uq.attach(study, SsdRootAnchor())
    report = pkg.uq.validate()
    assert "L3.bad-name" in codes(report, "error")


def test_l3_component_scope(pkg):
    study = make_study("Scoped", param="R0", observed=("V",))
    pkg.uq.attach(study, ElementAnchor(("battery",)))
    report = pkg.uq.validate()
    assert report.ok and not report.warnings, str(report)


def test_l3_ssv_overlay_names(pkg):
    good = make_study("Overlay", param="battery.R0", observed=())
    pkg.uq.attach(good, SsvAnchor("resources/params.ssv"))
    report = pkg.uq.validate()
    assert report.ok and not report.warnings, str(report)

    bad = make_study("Overlay2", param="battery.R1", observed=())
    pkg.uq.attach(bad, SsvAnchor("resources/params.ssv"))
    report = pkg.uq.validate()
    assert "L3.unknown-parameter" in codes(report, "warning")


PUNNED = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    version="2.0" name="Punned">
  <ssd:System name="root">
    <ssd:Elements>
      <ssd:System name="a">
        <ssd:Elements>
          <ssd:Component name="b"/>
        </ssd:Elements>
      </ssd:System>
      <ssd:Component name="a.b"/>
    </ssd:Elements>
  </ssd:System>
</ssd:SystemStructureDescription>
"""


def test_dotted_path_punning_is_ambiguous():
    host = SsdDocument("Punned.ssd", PUNNED.encode())
    assert host.resolve_dotted("a") == [("a",)]
    with pytest.raises(AmbiguousPathError):
        host.path_from_dotted("a.b")
    assert host.element_at(("a.b",)).get("name") == "a.b"
    assert host.element_at(("a", "b")).get("name") == "b"


def test_l1_catches_invalid_uq_document(pkg):
    # UncertainParameter without a distribution violates the uq schema
    bad = b"""<?xml version="1.0" encoding="UTF-8"?>
<uq:UncertaintyQuantification name="Bad"
    xmlns:uq="http://openscaling.org/UQ1/UncertaintyQuantification">
  <uq:Activities>
    <uq:ForwardUncertaintyQuantification>
      <uq:ParameterSet>
        <uq:Parameters>
          <uq:UncertainParameter name="x"/>
        </uq:Parameters>
      </uq:ParameterSet>
    </uq:ForwardUncertaintyQuantification>
  </uq:Activities>
</uq:UncertaintyQuantification>
"""
    pkg.add_entry("resources/uq/bad.uq.xml", bad)
    host = pkg.ssd()
    host.inject_metadata(
        host.root,
        "ssd_root",
        source="resources/uq/bad.uq.xml",
        mime="application/x-omuq",
        kind="quality",
    )
    pkg._mark_dirty(host.entry)
    report = pkg.uq.validate(level=1)
    assert not report.ok
    assert any(i.code == "L1.schema" for i in report.errors)
