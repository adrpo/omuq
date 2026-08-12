"""Author a complete DC-motor credibility study with the model builders.

This transcribes a real openScaling-style scenario (ScenarioDCMotor_ForwardUQ)
into omuq's typed builders: model provenance with modeling assumptions, two
deterministic verification activities with reference data, and a forward
uncertainty-quantification activity with fixed and uncertain parameters, an
operational domain with experiment points, requested results (percentiles and
Sobol indices), and a seeded Latin-hypercube sampling plan.

No model package for this study ships with the repo, so the script serializes
the document, re-parses it, and checks that the round trip is lossless. To
bind it to an actual DC-motor package, anchor it like any other study:

    pkg = SspPackage.open("DCMotor.ssp")
    pkg.uq.attach(study, SsdRootAnchor())
    assert pkg.uq.validate(level=3).ok   # names resolve against the SSD
    pkg.save("DCMotor.uq.ssp")

Run:    uv run examples/01_dc_motor.py
"""

from pathlib import Path

from omuq import model, parse_study, serialize_study
from omuq.model import (
    ExperimentPointsType,
    KeyValuesType,
    KeyValueType,
    OperationalDomainType,
    PointsType,
    Tparameter,
    Tunit,
    UnitsType,
)

OUT_DIR = Path(__file__).resolve().parent / "out"


def vendor_settings(**pairs: str) -> KeyValuesType:
    """Vendor-specific key/value block used on settings and sampling."""
    return KeyValuesType(
        type_value="com.3ds.uq",
        key_value=[KeyValueType(key=k, value=v) for k, v in pairs.items()],
    )


def dassl_setting() -> model.SimulationSettingType:
    setting = model.simulation_setting(
        stop_time=0.5, interval=0.001, tolerance=1e-6, method="dassl"
    )
    setting.key_values = vendor_settings(
        **{
            "translation.pedanticModeForCheckingModelicaSemantics": "true",
            "output.storeVariablesAtEvents": "true",
        }
    )
    return setting


def dc_motor_model() -> model.ModelType:
    """Model provenance and its modeling assumptions."""
    magnetic = model.assumption(
        "magneticSaturation",
        "Low magnetic saturation rate assumed: no magnetic saturation considered.",
        id="ma_01",
        origin="empirical",
    )
    thermal = model.assumption(
        "thermalEffects",
        "Limited electric and mechanical losses assumed: "
        "no thermal effects considered.",
        id="ma_02",
        origin="empirical",
    )
    # The builder has no argument for origin_ref, so assign it directly;
    # fields the builders do not cover can be set on the generated model.
    magnetic.origin_ref = "DCMotor_magnetic.pdf"
    thermal.origin_ref = "DCMotor_thermal.pdf"
    return model.model_info(
        name="ScenarioDCMotor",
        file="DCMotorUQExample_L3_causal.mo",
        model="modelica://DCMotorUQExample.ScenarioDCMotor",
        resource_meta_data="dc_motor.srmd",
        assumptions=model.modeling_assumptions("ma_dcmotor", [magnetic, thermal]),
    )


def verification(n: int, name: str, ref_name: str, ref_file: str):
    # The source scenario referenced a verification domain defined outside
    # the document. A dangling activityDomainRef fails level-2 validation
    # once attached, so it is omitted here.
    return model.verification(
        id=f"verif_{n:02d}",
        name=name,
        setting=dassl_setting(),
        reference=model.reference_data(
            [(ref_name, ref_file, "text/txt")],
            description="Solution from expm discretization",
        ),
    )


def fixed(name: str, value: float, unit: str) -> Tparameter:
    # ssv Real values are list-typed in the schema (one entry per dimension).
    return Tparameter(name=name, choice=Tparameter.Real(value=[value], unit=unit))


def forward_uq_activity():
    act = model.forward_uq(
        id="fuq_01",
        parameters=[
            fixed("dcMotor.d", 1e-4, "N.m.s/rad"),
            fixed("dcMotor.c_m", 0.01, "N.m/A"),
            fixed("dcMotor.c_g", 0.01, "V.s/rad"),
            fixed("dcMotor.J", 5.0e-5, "kg.m^2"),
        ],
        uncertain=[
            model.uncertain_parameter(
                "dcMotor.R",
                model.Normal(mu=0.1, sigma=0.01, unit="Ohm"),
                source="Estimated",
                source_info="From project XYZ",
            ),
            model.uncertain_parameter(
                "dcMotor.L",
                model.Uniform(minimum=1.05e-4, maximum=1.15e-4, unit="V.s/A"),
                source="Computed",
                source_info="From project XYZ",
            ),
        ],
        observed=["dcMotor.omega"],
        samples=256,
        desired=model.desired_results(
            mean=True,
            std=True,
            histogram=True,
            pdf=True,
            cdf=True,
            quantile=True,
            percentiles=[0.0, 0.05, 0.5, 0.95, 1.0],
            sobol_order=2,
            sobol_total=True,
            data="dc_motor.mat",
            summary="dc_motor_result_summary.xml",
            scope="Trajectory",
        ),
        setting=dassl_setting(),
    )
    # Set the distribution family used to summarize the observed variable.
    act.observed_variables.observed_variable[0].distribution_approximation = "Normal"
    # The parameter set declares the (V, T) region the parameters are valid
    # for, the experiment operating points, and the units.
    act.parameter_set.operational_domain = OperationalDomainType(
        axes=model.axes("V", "T", units={"V": "V", "T": "Nm"}),
        boundary=model.boundary(model.hyper_rectangle((0.0, 0.75), (10.0, 14.0))),
        experiment_points=ExperimentPointsType(
            point_set=[
                ExperimentPointsType.PointSet(
                    points=PointsType(
                        point=[
                            PointsType.Point(coordinates="12.0 0.0", id="fuq_01_P0"),
                            PointsType.Point(coordinates="12.0 0.0", id="fuq_01_P1"),
                        ]
                    )
                )
            ]
        ),
    )
    act.parameter_set.units = UnitsType(
        unit=[
            Tunit(name="kg.m^2", base_unit=Tunit.BaseUnit(kg=1, m=2)),
            Tunit(name="Ohm", base_unit=Tunit.BaseUnit(kg=1, m=2, s=-3, a=-2)),
            Tunit(name="N.m/A", base_unit=Tunit.BaseUnit(kg=1, m=2, s=-2, a=-1)),
            Tunit(
                name="rev/min",
                base_unit=Tunit.BaseUnit(rad=1, s=-1, factor=9.5492965855137),
            ),
        ]
    )
    # A seeded sampling plan makes the 256-sample study reproducible.
    model.sampling_of(act).key_values = vendor_settings(
        randomNumberGenerator="MT19937-64", randomNumberSeed="10"
    )
    return act


def main() -> None:
    study = model.study(
        "ScenarioDCMotor_ForwardUQ",
        activities=[
            verification(
                1,
                "Deterministic motor acceleration",
                "DCMotor_verif01_ref",
                "verification/verif_01/time_sol_verif01_ref.txt",
            ),
            verification(
                2,
                "Stochastic motor acceleration",
                "DCMotor_verif02_ref",
                "verification/verif_02/time_sol_verif_02_ref.txt",
            ),
            forward_uq_activity(),
        ],
    )
    study.activities.id = "act_01"
    study.model = dc_motor_model()

    payload = serialize_study(study)
    assert parse_study(payload) == study  # lossless round trip

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "dc_motor.uq.xml"
    out.write_bytes(payload)

    fuq = model.activity_of(study, "fuq_01")
    names = ", ".join(
        f"{p.name} ~ {type(model.distribution_of(p)).__name__}"
        for p in fuq.parameter_set.parameters.uncertain_parameter
    )
    print(f"study: {study.name} ({len(model.activities_of(study))} activities)")
    print(f"uncertain: {names}")
    print(f"observed: {', '.join(model.observed_names(fuq))}")
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
