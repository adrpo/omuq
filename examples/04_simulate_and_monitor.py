"""Simulate the domain-annotated package from 03 and monitor it live.

Reads the study, domains, and SimulationSetting from
examples/out/ScrewTrajectory.uq.ssp, runs it, streams samples to stdout and
a CSV, and counts domain-of-validation exits. The run's results, an
envelope fitted to the run, and a coverage classification are then written
back into a new package.

Pass --ui to watch the run live in the browser.

Run:     uv run --extra geometry examples/03_author_domains.py   # the input
         uv run --extra geometry examples/04_simulate_and_monitor.py [--ui]
"""

from __future__ import annotations

import sys
from pathlib import Path

from omuq import (
    CsvSink,
    MemorySink,
    PrintSink,
    Simulation,
    SspPackage,
    coverage_from_result,
    fit_activity_domain,
    model,
)

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"
INPUT = OUT_DIR / "ScrewTrajectory.uq.ssp"
CSV_OUT = OUT_DIR / "screw_trajectory_sim.csv"
RESULTS_OUT = OUT_DIR / "ScrewTrajectory.uq.results.ssp"

# Also defined in 03_author_domains.py; the examples are standalone
# scripts and do not share code.
OBSERVED = ("nonlinearMixer1.u3", "nonlinearMixer1.y2", "screwTrajectory1.x")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT.is_file():
        raise SystemExit("run examples/03_author_domains.py first")

    pkg = SspPackage.open(INPUT)
    sim = Simulation.from_package(pkg)

    mem = MemorySink()
    # on_violation fires once per sample outside the domain (see
    # SIMULATION.md section 5), so this list counts violations, not
    # exits/excursions; the two are reported separately below.
    dov_violations: list = []
    sim.subscribe(mem)
    sim.subscribe(PrintSink(every=50))
    sim.subscribe(CsvSink(CSV_OUT))
    sim.on_violation(dov_violations.append, only="Validation")

    ui = sim.watch() if "--ui" in sys.argv[1:] else None
    result = sim.run()
    print(result.summary())
    print(
        "domain-of-validation violations collected via on_violation: "
        f"{len(dov_violations)}"
    )
    print(f"domain-of-validation exits: {result.exits['domainOfValidation']}")
    if ui is not None:
        ui.wait()

    # -- write the run back into the study ----------------------------------
    attached = pkg.uq.study(0)
    pkg.uq.record_result(attached, result, samples=mem.samples)
    # pad=1e-3: a zero-margin box (the default) can reject some of its own
    # calibration samples once monitored, since formatting rounds boundaries
    # by up to one quantization step but monitor() checks at tol=1e-9 (see
    # SIMULATION.md section 5 and fitting.py's Precision section).
    envelope = fit_activity_domain(
        mem.samples,
        OBSERVED,
        id="runEnvelope",
        kind="Validation",
        shape="box",
        pad=1e-3,
    )
    model.add_domain(attached.document, envelope)
    model.upsert_coverage(
        attached.document,
        coverage_from_result(
            result,
            requested="domainOfValidation",
            realized="runEnvelope",
            when_violated="AcceptableRisk",
        ),
    )
    pkg.uq.update(attached)

    report = pkg.uq.validate(level=3)
    if not report.ok:
        raise SystemExit(f"validation failed:\n{report}")
    pkg.save(RESULTS_OUT)
    print(f"artifacts: {CSV_OUT}, {RESULTS_OUT}")


if __name__ == "__main__":
    main()
