# omuq-python

Attach, read, and validate omuq (openScaling Uncertainty Quantification)
and credibility data in spec-conforming SSP packages, and run the attached
studies: OMSimulator-driven simulation with domain monitoring, CSV
streaming, and a browser-based web UI. omuq documents
link to SSP hosts through standard SSP 2.0 `ssc:MetaData` elements, so the
result is a plain `.ssp` that any SSP tool can open.

* Entries that were not modified are written back unchanged. Modified SSD
  and SSV files are edited with lxml, which preserves existing comments,
  annotations, and formatting.
* MetaData links are inserted at the schema-correct position and the host
  is stamped `version="2.0"`.
* Validation runs at three levels: schema, links, and name resolution.
* Domain fitting builds convex-hull or box boundaries from a run's
  samples, with inflation, padding, and a precision-loss guard.
* Results write-back stores a run's domain-violation counts, sample
  table, and coverage judgment in the same document; writes are
  checksummed and idempotent.

See `docs/IMPLEMENTATION_GUIDELINE.md` for the normative conventions this
SDK implements and `docs/SIMULATION.md` for the simulation runtime.

## Install

```bash
uv venv && uv pip install -e .          # editable install, runtime deps only
# or: pip install -e .
```

| Extra | Adds | For |
| --- | --- | --- |
| `geometry` | `scipy` | convex-hull domains and hull fitting (`fit_operational_domain`/`fit_activity_domain`) |
| `sim` | `OMSimulator` | in-process simulation (no macOS wheels; use `DockerOMSimulatorDriver` instead) |
| `dev` | `pytest`, `ruff`, the `xsdata` CLI | running the tests and regenerating the schema model |

Combine as needed, e.g. `uv pip install -e ".[geometry,dev]"`.

## Running the examples

`uv run` creates the environment on first use, installs the package with
its dependencies, and runs the script, so a fresh clone needs no separate
install step:

```bash
uv run examples/01_dc_motor.py                                # author the DC-motor study
uv run examples/02_quickstart.py                              # domain monitoring without a simulator
uv run --extra geometry examples/03_author_domains.py         # fit domains from a run
uv run --extra geometry examples/04_simulate_and_monitor.py   # simulate 03's package, write back
uv run examples/05_uncertain_parameters.py                    # attach to one SSD element
```

`--extra geometry` installs scipy, which the convex-hull fitting in
example 03 uses; without it the fitted domains are boxes. Example 04
reads the package example 03 writes
(`examples/out/ScrewTrajectory.uq.ssp`), so run 03 first. Outputs land in
`examples/out/`. On a machine without OMSimulator or Docker the
simulating examples fall back to a built-in waveform driver, so every
example runs anywhere.

Example 04 accepts `--ui`, which opens a browser page that streams the
samples and violations during the run:

```bash
uv run --extra geometry examples/04_simulate_and_monitor.py --ui
```

After the run the page stays open until the script is stopped with
Ctrl+C.

`uv run` writes `uv.lock` next to `pyproject.toml`; the file is
gitignored. With an environment installed manually
(`uv venv && uv pip install -e ".[geometry]"`), the same scripts also run
as `python examples/01_dc_motor.py` or
`uv run --no-sync python examples/01_dc_motor.py`.

## A first study: the DC motor

A credibility study is a typed document, authored with the builders in
`omuq.model`. This one describes forward uncertainty propagation through a
DC-motor model with two uncertain electrical parameters:

```python
from omuq import model, parse_study, serialize_study

study = model.study(
    "ScenarioDCMotor_ForwardUQ",
    activities=[
        model.forward_uq(
            id="fuq_01",
            uncertain=[
                model.uncertain_parameter(
                    "dcMotor.R",
                    model.Normal(mu=0.1, sigma=0.01, unit="Ohm"),
                    source="Estimated",
                ),
                model.uncertain_parameter(
                    "dcMotor.L",
                    model.Uniform(minimum=1.05e-4, maximum=1.15e-4, unit="V.s/A"),
                    source="Computed",
                ),
            ],
            observed=["dcMotor.omega"],
            samples=256,
            desired=model.desired_results(mean=True, std=True, sobol_order=2),
            stop=0.5,
            step=0.001,
            tolerance=1e-6,
            method="dassl",
        )
    ],
)

payload = serialize_study(study)  # schema-conforming omuq XML
assert parse_study(payload) == study  # lossless round trip
print(payload.decode().splitlines()[1][:76], "...")
```

The full scenario (model provenance with modeling assumptions, two
verification activities with reference data, an operational domain with
experiment points, unit declarations, and a seeded sampling plan) is
`examples/01_dc_motor.py`. Attach the result to the SSP that carries the
model (`pkg.uq.attach(study, SsdRootAnchor())`) and `pkg.uq.validate(level=3)`
checks every referenced variable against the SSD.

## Quickstart: domain monitoring

```python
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
```

This runs without a simulator, input files, or scipy: `FunctionDriver`
stands in for OMSimulator and the domain is a `HyperRectangle`. Run
`uv run examples/02_quickstart.py`; the signal leaves `operatingBox`
during the run, and the violation and a run summary are printed.

## The full workflow

A typical session has six stages; each is covered by an example script:

1. **Author** a study (parameters, activities, domains) with the
   builders in `omuq.model` (`examples/01_dc_motor.py`), or fit its
   domains from a reference run (`examples/03_author_domains.py`).
2. **Attach** it: `pkg.uq.attach(study, anchor)`.
3. **Validate** it: `pkg.uq.validate()`.
4. **Simulate** it back (`examples/04_simulate_and_monitor.py`).
5. **Monitor** domains live: `sim.on_violation(...)`, or watch it in the
   browser with `sim.watch()`.
6. **Write back** the results, a fitted envelope domain, and a coverage
   judgment: `pkg.uq.record_result(...)`, `pkg.uq.update(...)`.

```python
sim = Simulation.from_package("model.uq.ssp", fallback_driver=FunctionDriver(demo))
sim.subscribe(MemorySink())
result = sim.run()
print(result.summary())
```

`examples/05_uncertain_parameters.py` runs the same attach, validate,
read-back, and detach cycle anchored on a single SSD element instead of
the system root, for a study whose subject is one component's parameter.

## Reading and validating packages

```python
pkg = SspPackage.open("model.uq.ssp")
for attached in pkg.uq.studies():
    print(attached.anchor, attached.name, len(attached.activities))
one = pkg.uq.study("BatteryUQ")  # or by position: pkg.uq.study(0)
```

`AttachedStudy` carries `.anchor`, `.entry` (`None` when stored inline),
`.source`/`.kind`/`.mime` (the raw MetaData attributes), and `.document`;
`.name`/`.activities`/`.domains` alias the document. `pkg.uq.detach(...)`
removes the link and garbage-collects the document once nothing else
references it.

`pkg.uq.validate(level=1..3)` returns a `ValidationReport` (`.ok`,
`.errors`, `.warnings`), issues coded `L1.*` to `L3.*`:

* **Level 1 (schema)**: every omuq document, and every host document
  carrying an omuq link, validates against its XSD set.
* **Level 2 (links)**: MetaData sources resolve inside the package,
  external sources resolve and match their checksums, and in-document
  references (`domainRef`, `requestedDomainRef`, ids, ...) point at
  something that exists.
* **Level 3 (names)**: every parameter, observed-variable, and
  calibration-target name resolves inside its anchor's scope (or against
  the host SSV's declared parameters, for an SSV overlay).

See `docs/IMPLEMENTATION_GUIDELINE.md` for the full normative rules.

### Anchors

| Anchor | Meaning | Name scope inside the study |
| --- | --- | --- |
| `SsdRootAnchor()` | whole system structure | hierarchical from the root system (`plant.battery.R0`) |
| `ElementAnchor(("battery",))` | one System/Component | relative to that element (`R0`) |
| `ParameterBindingAnchor(path, index)` | one parameter binding | same scope as the owning element |
| `SsvAnchor("resources/params.ssv")` | an SSV parameter set | parameter names of that SSV (distribution overlay) |

`ElementAnchor` paths are tuples because SSP element names may contain
dots. `pkg.ssd().path_from_dotted("plant.battery")` converts a dotted
string and raises `AmbiguousPathError` when the name is ambiguous.

## Simulation and monitoring

`Simulation.from_package(package, study=0, activity=0, driver=None, ...)`
resolves the study and activity in one call and takes the time grid from
the most specific source available: an explicit
`step=`/`stop=`/`start=`, else the activity's `SimulationSetting`, else
(`stop`/`start` only) the SSD's `DefaultExperiment`. Unless `driver=` is
given, a backend is selected with `auto_driver()` (see Drivers below).

### Drivers

A driver is the backend that produces the sample values. `Simulation`
accepts any object with the four-method protocol described in
`docs/SIMULATION.md` section 1; the SDK ships three:

| Driver | Backend |
| --- | --- |
| `OMSimulatorDriver(inst)` | an OMSimulator model instantiated in this process (needs the `sim` extra; no macOS wheels) |
| `DockerOMSimulatorDriver(ssp_path)` | OMSimulator inside the `omuq-omsimulator` container (see `docker/README.md`) |
| `FunctionDriver(fn)` | a Python function of time; no simulator, no input files |

`auto_driver(ssp_path)` probes in order: OMSimulator's Python bindings in
this interpreter, then the Docker image. It returns the first backend
that is available, or `fallback=` if none is, or raises
`DriverNotFoundError` naming what was probed and how to fix it.
`Simulation.from_package` calls it when no `driver=` is passed.

`FunctionDriver` computes each observed variable from the time `t`, so a
script or test runs without OMSimulator installed:

```python
driver = FunctionDriver(lambda t: {"speed": 2.0 * t, "torque": 1.0})
```

The function returns either a mapping by variable name, as above, or a
sequence in the observed-variable order.

### Sinks

A sink observes the run sample by sample. Register any number of them
with `sim.subscribe(...)`; each receives `on_start(names)` once, then
`on_sample(sample)` per sample, then `on_finish()`. A plain callable can
be subscribed too; it is called with each sample.

| Sink | Effect |
| --- | --- |
| `PrintSink(every=50, precision=4)` | prints every 50th sample; a sample outside a monitored domain gets a `[!domainId]` marker |
| `CsvSink("run.csv")` | writes `time,<name>,...` rows; `samples_from_csv` reads the file back |
| `MemorySink()` | keeps the run's names and samples in memory |

`MemorySink` is how a run's data reaches the rest of the SDK: after
`sim.run()`, pass `mem.samples` to `fit_operational_domain(...)` to fit a
domain from the run, or to `pkg.uq.record_result(..., samples=mem.samples)`
to store the sample table in the package.

`sim.on_violation(fn, only="Validation")` calls `fn` once per sample that
falls outside a monitored domain, optionally filtered by domain id or
kind.

Each monitored domain reports two counts: `samples_outside` (how many
samples fell outside it, the count that drives `on_violation`) and `exits`
(how many separate excursions, that is, inside-to-outside transitions,
occurred). See `docs/SIMULATION.md` for the full protocol, backend
selection, and monitoring semantics.

## Domain fitting

An operational domain states the region of the observed variables in
which the model is claimed valid; during simulation, every sample is
checked against it. The boundary can be written by hand, point by point,
or fitted from data: run the model once as a reference, record the
samples with a `MemorySink`, and compute a shape that encloses them.

```python
mem = MemorySink()
sim.subscribe(mem)
sim.run()

domain = fit_operational_domain(
    mem.samples, OBSERVED, id="operationalDomain", inflate=0.25
)
```

The input point cloud can be samples, a `name -> series` mapping, or raw
tuples. Two shapes can be fitted; for the 2-D points (1, 1), (2, 3),
(3, 1):

* `shape="box"` takes the per-axis min/max: the rectangle
  [1, 3] x [1, 3]. Pure Python, works everywhere, but it includes the
  corner (1, 3) that the data never reached.
* `shape="hull"` (the default) computes the convex hull: the triangle
  through the three points. Tighter around the data, but computing and
  checking hulls requires scipy, which is what the `geometry` extra
  installs.
* `shape="auto"` tries the hull and falls back to a box when scipy is
  missing or the points are degenerate.

Two arguments adjust what is fitted. `inflate=0.25` scales the shape 25%
outward about its centroid: a boundary drawn exactly on one reference run
would report every small deviation of the next run as a violation, so
some margin is usually wanted. `time_window=(None, 1.0)` fits only from
the samples with `t <= 1.0`, which is how example 03 builds a domain of
validation that covers the early regime alone.

`fit_activity_domain(...)` fits an `ActivityDomain` the same way, with
`domain=` pointing at the operational domain it narrows.

## Results write-back

```python
pkg.uq.record_result(attached, result, samples=mem.samples)
```

Writes the run's domain-violation counts and sample count as `ErrorMetric`
results, plus (given `samples`) a checksummed CSV under `resources/uq/`
and, when `DesiredResults` asks for one, a per-variable `Normal(mu, sigma)`
summary. Recording the same result again is idempotent and byte-stable:
each call replaces the activity's whole result set rather than appending
to it, so no duplicate entries are added.
`coverage_from_result(result, requested=..., realized=..., when_violated=...)`
builds a `DomainCoverage` from the run's counts: a run with no violations
is classified `"Covered"` automatically; a run that left the domain is
not, and must be classified manually. See `docs/SIMULATION.md` section 7
for the full write-back walkthrough.

## Live web UI

```python
ui = sim.watch()  # before run(): opens the browser, starts a local server
result = sim.run()
ui.wait()  # after run(): keep the page open until Ctrl+C
```

The page streams traces and violations during the run and renders 3-D
domain boundaries (rectangles and hulls). A tab opened late or refreshed
replays the run from the start. The server uses only the standard library
and binds to `127.0.0.1` by default.

## Docker driver

OMSimulator has no macOS build; `DockerOMSimulatorDriver` runs it inside a
container while the SDK (monitoring, sinks, the web UI) stays on the
host. See `docker/README.md` for building the image and driving a run.

## Development

```bash
uv pip install -e ".[dev,geometry]"
pytest
ruff check . && ruff format --check .
```

The typed model in `src/omuq/model/_generated.py` is produced by xsdata
from `src/omuq/schemas/uq/`. Regenerate after a schema update:

```bash
xsdata generate src/omuq/schemas/uq/UncertaintyQuantification.xsd \
    --package omuq.model --structure-style single-package \
    --compound-fields --relative-imports
mv omuq/model.py src/omuq/model/_generated.py && rm -rf omuq
```

Regeneration can change xsdata's compound-field names (for example
`ActivitiesType.choice`). Those names are written only in
`src/omuq/model/__init__.py`; update them there and run the test suite.

## License and attribution

TBD
