"""Smoke tests for the examples: each runs as a subprocess.

These stay fast because every simulating example resolves to the
demo-waveform fallback path on a machine without OMSimulator/docker (see
``auto_driver``), and stop=10.0/step=0.01 is only 1001 samples. Example 04
reads back 03's output package, so its test runs 03 first; since the suite
also runs 03 on its own, 03 is exercised twice in a row.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
OUT = EXAMPLES / "out"


def run_example(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EXAMPLES / name), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_01_dc_motor_writes_a_schema_valid_study():
    result = run_example("01_dc_motor.py")
    assert result.returncode == 0, result.stderr
    out = OUT / "dc_motor.uq.xml"
    assert out.is_file()
    assert "dcMotor.R ~ Normal" in result.stdout

    # The emitted document must validate against the bundled omuq schema.
    from importlib import resources

    from lxml import etree

    with resources.as_file(
        resources.files("omuq.schemas.uq") / "UncertaintyQuantification.xsd"
    ) as p:
        schema = etree.XMLSchema(etree.parse(str(p)))
    assert schema.validate(etree.parse(str(out))), schema.error_log


def test_02_quickstart_prints_a_violation():
    result = run_example("02_quickstart.py")
    assert result.returncode == 0, result.stderr
    assert "outside" in result.stdout


def test_03_author_domains_writes_the_annotated_package():
    result = run_example("03_author_domains.py")
    assert result.returncode == 0, result.stderr
    assert (OUT / "ScrewTrajectory.uq.ssp").is_file()


def test_04_simulate_and_monitor_writes_csv_and_results():
    # 04 reads 03's output, so run 03 first here too. This also checks that
    # 03 can be run twice in a row.
    setup = run_example("03_author_domains.py")
    assert setup.returncode == 0, setup.stderr

    result = run_example("04_simulate_and_monitor.py")
    assert result.returncode == 0, result.stderr
    assert (OUT / "screw_trajectory_sim.csv").is_file()
    assert (OUT / "ScrewTrajectory.uq.results.ssp").is_file()


def test_04_labels_the_on_violation_count_honestly_as_violations_not_exits():
    """Regression: on_violation(only="Validation") fires once per
    sample outside the domain (see SIMULATION.md section 5), so
    the count it collects is a violation/samples-outside count, not an exit
    (excursion) count. Cross-checked against summary()'s own line, which
    already reports both numbers correctly.
    """
    setup = run_example("03_author_domains.py")
    assert setup.returncode == 0, setup.stderr

    result = run_example("04_simulate_and_monitor.py")
    assert result.returncode == 0, result.stderr
    stdout = result.stdout

    outside, excursions = (
        int(n)
        for n in re.search(
            r"domainOfValidation: (\d+) samples outside in (\d+) excursion",
            stdout,
        ).groups()
    )
    violations = int(re.search(r"violations collected[^:]*:\s*(\d+)", stdout).group(1))
    exits = int(
        re.search(r"^domain-of-validation exits:\s*(\d+)", stdout, re.M).group(1)
    )

    # what on_violation actually collected: one DomainViolation per sample.
    assert violations == outside
    # the "exits" label must report true excursions, not the raw per-sample
    # violations count the buggy version printed under that name.
    assert exits == excursions
    assert exits != violations


def test_05_uncertain_parameters_writes_the_forward_uq_package():
    result = run_example("05_uncertain_parameters.py")
    assert result.returncode == 0, result.stderr
    assert (OUT / "ScrewTrajectory.forward_uq.ssp").is_file()
