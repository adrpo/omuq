"""Quickstart: build a study, run it, and observe a domain violation.

Uses a rectangular domain and a driver whose signal leaves it partway
through the run. Requires no simulator, input files, or scipy.

Install: uv venv && uv pip install -e ".[geometry]"
Run:     uv run examples/02_quickstart.py
"""

from __future__ import annotations

from omuq import FunctionDriver, PrintSink, Simulation, model


def main() -> None:
    # Ramps from inside [-2, 2] to well outside it by t=10.
    driver = FunctionDriver(lambda t: [-1.0 + 0.5 * t])
    domain = model.operational_domain(
        "operatingBox", ["signal"], model.hyper_rectangle([-2.0], [2.0])
    )
    study = model.study(
        "QuickstartStudy",
        activities=[model.forward_uq(observed=["signal"], stop=10.0, step=1.0)],
        domains=[domain],
    )

    sim = Simulation.for_study(study, driver)
    sim.subscribe(PrintSink(every=2))
    sim.on_violation(print)
    result = sim.run()
    print(result.summary())


if __name__ == "__main__":
    main()
