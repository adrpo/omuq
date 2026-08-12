"""Attach an uncertain-parameter study directly to one SSD element.

Where 03/04 declare domains at the SSD root, this example attaches at a
single element (screwTrajectory1): names inside the study resolve relative
to that element, so the uncertain parameter is "omega", not
"screwTrajectory1.omega" (see omuq.ElementAnchor). Also demonstrates the
read-back surface -- AttachedStudy.name/.activities -- and detach().

Run:     uv run examples/05_uncertain_parameters.py
"""

from __future__ import annotations

from pathlib import Path

from omuq import ElementAnchor, SspPackage, model

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "ScrewTrajectory.ssp"
OUT_DIR = HERE / "out"
OUTPUT = OUT_DIR / "ScrewTrajectory.forward_uq.ssp"

# "omega" (screwTrajectory1's own connector name) resolves under this anchor
# without a "screwTrajectory1." prefix -- see the module docstring.
ANCHOR = ElementAnchor(("screwTrajectory1",))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    omega = model.uncertain_parameter(
        "omega", model.Normal(mu=2.0, sigma=0.1), source="Measured"
    )
    study = model.study(
        "ScrewTrajectoryOmegaUQ",
        activities=[
            model.forward_uq(uncertain=[omega], observed=["x", "y", "z"], samples=200)
        ],
        info="Forward UQ over the helix's angular frequency",
    )

    pkg = SspPackage.open(FIXTURE)
    pkg.uq.attach(study, ANCHOR)
    report = pkg.uq.validate(level=3)
    if not report.ok:
        raise SystemExit(f"validation failed:\n{report}")
    pkg.save(OUTPUT)
    print(f"saved: {OUTPUT}")

    reopened = SspPackage.open(OUTPUT)
    studies = reopened.uq.studies()
    for attached in studies:
        n = len(attached.activities)
        print(f"{attached.anchor}: {attached.name!r} ({n} activity)")

    before = len(reopened.entry_names())
    reopened.uq.detach(studies[0])
    print(f"entries after detach: {len(reopened.entry_names())} (was {before})")


if __name__ == "__main__":
    main()
