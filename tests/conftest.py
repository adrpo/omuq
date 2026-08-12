import io
import sys
import textwrap
import zipfile

import pytest

SSD = """<?xml version="1.0" encoding="UTF-8"?>
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
    version="1.0" name="Demo">
  <ssd:System name="plant">
    <ssd:Connectors>
      <ssd:Connector name="T_amb" kind="parameter">
        <ssc:Real/>
      </ssd:Connector>
    </ssd:Connectors>
    <ssd:ParameterBindings>
      <ssd:ParameterBinding source="resources/params.ssv"/>
    </ssd:ParameterBindings>
    <!-- vendor comment that must survive round trips -->
    <ssd:Elements>
      <ssd:Component name="battery" source="resources/battery.fmu"
          type="application/x-fmu-sharedlibrary">
        <ssd:Connectors>
          <ssd:Connector name="R0" kind="parameter">
            <ssc:Real/>
          </ssd:Connector>
          <ssd:Connector name="V" kind="output">
            <ssc:Real/>
          </ssd:Connector>
        </ssd:Connectors>
        <ssd:Annotations>
          <ssc:Annotation type="com.vendor.x">
            <v:foo xmlns:v="urn:vendor" keep="me"/>
          </ssc:Annotation>
        </ssd:Annotations>
      </ssd:Component>
    </ssd:Elements>
  </ssd:System>
  <ssd:DefaultExperiment startTime="0.0" stopTime="1.0"/>
</ssd:SystemStructureDescription>
"""

SSV = """<?xml version="1.0" encoding="UTF-8"?>
<ssv:ParameterSet
    xmlns:ssv="http://ssp-standard.org/SSP1/SystemStructureParameterValues"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
    version="1.0" name="Params">
  <ssv:Parameters>
    <ssv:Parameter name="battery.R0">
      <ssv:Real value="0.05"/>
    </ssv:Parameter>
  </ssv:Parameters>
</ssv:ParameterSet>
"""

EXTRA = b"third-party bytes that must be preserved verbatim\n"
FMU = b"PK\x03\x04 not really an fmu, content only matters as bytes"


def build_ssp(ssd: str = SSD) -> bytes:
    """The fixture archive; ``ssd`` allows SSD variants (e.g. no DefaultExperiment)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SystemStructure.ssd", ssd)
        zf.writestr("resources/params.ssv", SSV)
        zf.writestr("resources/battery.fmu", FMU)
        zf.writestr("extra/com.vendor.tool/notes.txt", EXTRA)
    return buf.getvalue()


@pytest.fixture()
def ssp_bytes() -> bytes:
    return build_ssp()


@pytest.fixture()
def pkg(ssp_bytes):
    from omuq import SspPackage

    return SspPackage.open(io.BytesIO(ssp_bytes))


def make_study(name="BatteryUQ", param="battery.R0", observed=("battery.V",)):
    from omuq import model

    return model.study(
        name,
        activities=[
            model.forward_uq(
                uncertain=[
                    model.uncertain_parameter(
                        param,
                        model.Normal(mu=0.05, sigma=0.005),
                        source="Measured",
                    )
                ],
                observed=list(observed),
                samples=100,
            )
        ],
        info="fixture study",
    )


def reopen(pkg):
    """Save a package to memory and open the result again."""
    import io as _io

    from omuq import SspPackage

    buf = _io.BytesIO()
    pkg.save(buf)
    buf.seek(0)
    return SspPackage.open(buf), buf.getvalue()


# -- simulation fakes and document helpers ---------------------------------
#
# Single copies shared by every simulation test module, written on the
# omuq.model builders so that the tests exercise the public construction
# path instead of the generated classes' compound fields.


class FakeDriver:
    """Deterministic: value of the i-th name at time t is t + 10*i."""

    def __init__(self):
        self.calls = []
        self._t = None

    def initialize(self, start, stop, step, names):
        self.calls.append(("initialize", start, stop, step, tuple(names)))
        self._t = start

    def advance(self, t):
        self.calls.append(("advance", t))
        self._t = t

    def read(self, names):
        self.calls.append(("read", tuple(names)))
        return [self._t + 10 * i for i in range(len(names))]

    def terminate(self):
        self.calls.append(("terminate",))


def make_activity(
    observed=("a", "b"), interval=None, stop_time=None, with_setting=True
):
    """A ForwardUQ activity; ``with_setting=False`` drops the SimulationSetting."""
    from omuq import model

    if not with_setting:
        return model.forward_uq(observed=list(observed))
    return model.forward_uq(observed=list(observed), step=interval, stop=stop_time)


def rect_boundary(lo, hi):
    from omuq import model

    return model.boundary(model.hyper_rectangle(lo, hi))


def hull_boundary(points):
    from omuq import model

    return model.boundary(model.convex_hull(points))


def rect_domain(id="dov", names=("a",), lo=(0.0,), hi=(0.25,), kind="Validation"):
    """An ActivityDomain over a box, defaulting to a domain of validation."""
    from omuq import model

    return model.activity_domain(
        id, list(names), model.hyper_rectangle(lo, hi), kind=kind
    )


def op_domain(id="od", names=("a",), lo=(0.0,), hi=(1.0,)):
    """A modeled TypedOperationalDomain over a box."""
    from omuq import model

    return model.operational_domain(id, list(names), model.hyper_rectangle(lo, hi))


def study_with_domains(observed=("a", "b"), *, name="SimStudy", bare=False):
    """A study whose domains cover the monitored and the skippable cases.

    ``od`` is monitorable, ``dov`` is left mid-run, ``paramDomain`` is over a
    variable this run does not observe, and ``bare`` (opt-in) has neither
    axes nor a boundary.
    """
    from omuq import model

    items = [
        op_domain("od", observed, (-100.0,) * len(observed), (100.0,) * len(observed)),
        rect_domain("dov", observed[:1], (0.0,), (0.25,)),
        rect_domain(
            "paramDomain", ("someParameter",), (0.0,), (1.0,), kind="Calibration"
        ),
    ]
    if bare:
        items.append(model.ActivityDomainType(id="bare", kind="Validation"))
    return model.study(
        name,
        activities=[make_activity(observed=observed, interval=0.25, stop_time=1.0)],
        domains=items,
    )


# -- the fake container runner (DockerOMSimulatorDriver stream protocol) ---

FAKE_RUNNER = textwrap.dedent(
    """
    import sys

    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    names = args["--names"].split(",")
    start = float(args["--start"])
    stop = float(args["--stop"])
    step = float(args["--step"])
    mode = args.get("--fake-mode", "ok")

    if mode == "no-handshake":
        print("hello world", flush=True)
        sys.exit(0)

    if mode == "noisy":
        print("info: some simulator chatter", flush=True)
        print("warning: more chatter", flush=True)

    print(f"#omuq-sim v1 names={args['--names']}", flush=True)
    eps = step * 1e-9
    t = start
    i = 0
    emitted = 0
    while True:
        shown = t + (step / 2 if mode == "diverge" and emitted == 2 else 0.0)
        print(
            ",".join([repr(shown)] + [repr(t + 10 * j) for j in range(len(names))]),
            flush=True,
        )
        emitted += 1
        if mode == "die" and emitted == 2:
            print("boom: solver exploded", file=sys.stderr, flush=True)
            sys.exit(3)
        if t >= stop - eps:
            break
        i += 1
        t = start + i * step
        if t > stop:
            t = stop
    """
)


@pytest.fixture()
def fake_runner(tmp_path):
    """Build DockerOMSimulatorDrivers that speak to a local python runner."""
    from omuq import DockerOMSimulatorDriver

    script = tmp_path / "fake_runner.py"
    script.write_text(FAKE_RUNNER)
    ssp = tmp_path / "model.ssp"
    ssp.write_bytes(b"not a real ssp; never opened by the fake runner")

    def build(mode="ok", **kwargs):
        cmd = [sys.executable, str(script)]
        if mode != "ok":
            cmd += ["--fake-mode", mode]
        return DockerOMSimulatorDriver(ssp, command=cmd, timeout=10.0, **kwargs)

    return build
