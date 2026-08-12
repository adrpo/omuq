"""Fit domains from a reference run, then attach them to the ScrewTrajectory demo.

Runs the model once over t in [0, 10] (falls back to a small deterministic
waveform when no OMSimulator/docker backend is installed -- see demo_wave),
fits a modeled operational domain to the whole run (+25%) and a domain of
validation to its early regime t <= 1.0 (+10%), then attaches both to a
study saved alongside the input .ssp.

The domains are fitted from this run with this backend.
04_simulate_and_monitor.py resolves the same backend, so its monitoring
against these domains passes by construction.

Run:     uv run --extra geometry examples/03_author_domains.py
"""

from __future__ import annotations

import math
from pathlib import Path

from omuq import (
    FunctionDriver,
    MemorySink,
    Simulation,
    SsdRootAnchor,
    SspPackage,
    auto_driver,
    fit_activity_domain,
    fit_operational_domain,
    model,
)

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "ScrewTrajectory.ssp"
OUT_DIR = HERE / "out"
OUTPUT = OUT_DIR / "ScrewTrajectory.uq.ssp"

STOP_TIME = 10.0
STEP = 0.01

# Also defined in 04_simulate_and_monitor.py; the examples are standalone
# scripts and do not share code.
OBSERVED = ("nonlinearMixer1.u3", "nonlinearMixer1.y2", "screwTrajectory1.x")


def demo_wave(t: float) -> list[float]:
    """Deterministic stand-in for the FMUs, used with no OMSimulator backend."""
    return [
        -4.6 + 1.3 * t,
        0.3 + 0.35 * math.cos(2.0 * t),
        -3.0 - 1.6 * t + 0.3 * math.sin(3.0 * t),
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pkg = SspPackage.open(FIXTURE)
    driver = auto_driver(
        FIXTURE, system=pkg.ssd().system_name, fallback=FunctionDriver(demo_wave)
    )

    mem = MemorySink()
    sim = Simulation(driver, OBSERVED, stop=STOP_TIME, step=STEP)
    sim.subscribe(mem)
    sim.run()

    od = fit_operational_domain(
        mem.samples, OBSERVED, id="operationalDomain", inflate=0.25, shape="auto"
    )
    dov = fit_activity_domain(
        mem.samples,
        OBSERVED,
        id="domainOfValidation",
        domain=od,
        time_window=(None, 1.0),
        inflate=0.10,
        shape="auto",
    )
    for fitted in (od, dov):
        # ActivityDomain has no geometryKind; read the shape back for both.
        is_hull = isinstance(model.shape_of(fitted), model.ConvexHullType)
        n = len(model.points_of(fitted))
        print(f"fitted {fitted.id}: {'hull' if is_hull else 'box'} ({n} points)")

    study = model.study(
        "ScrewTrajectoryDomains",
        activities=[
            model.validation(observed=list(OBSERVED), stop=STOP_TIME, step=STEP)
        ],
        domains=[od, dov],
        info="Operational domain and domain of validation fitted from a reference run",
    )
    pkg.uq.attach(study, SsdRootAnchor())

    report = pkg.uq.validate(level=3)
    if not report.ok:
        raise SystemExit(f"validation failed:\n{report}")
    pkg.save(OUTPUT)
    print(f"saved: {OUTPUT}")


if __name__ == "__main__":
    main()
