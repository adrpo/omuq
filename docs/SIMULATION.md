# Simulation Runtime

This is the runtime counterpart to `docs/IMPLEMENTATION_GUIDELINE.md`. That
document specifies how omuq data is stored and linked inside an SSP
package; this one specifies what `omuq.Simulation` does when it drives a
study over time: the driver and stream protocols, backend selection, sinks,
domain-monitoring semantics, the live web UI, and how a finished run is
written back. It is derived from the behavior of `drivers.py`,
`simulation.py`, `webui/`, and `writeback.py`; where this document and the
code disagree, the code is authoritative.

See the README for the everyday API (`Simulation.for_study`,
`Simulation.from_package`, `sim.watch()`, `pkg.uq.record_result`); this
document is the reference for exactly how each of those behaves.

## 1. Driver protocol

A simulator backend is any object implementing the duck-typed
`omuq.SimulationDriver` protocol: four methods, called by `Simulation.run()`
and nothing else:

```python
class SimulationDriver(Protocol):
    def initialize(
        self, start: float, stop: float, step: float, names: Sequence[str]
    ) -> None: ...
    def advance(self, t: float) -> None: ...
    def read(self, names: Sequence[str]) -> list[float]: ...
    def terminate(self) -> None: ...
```

* **`initialize`**: configure the model for the time span `[start, stop]`
  at communication step `step`, and prepare to report `names` (the
  activity's observed variables, in declaration order).
* **`advance(t)`**: step the model to the absolute target time `t`, not
  a delta. Grid arithmetic (where the next communication point falls) is
  done in `Simulation`; a driver receives only the target time.
* **`read(names)`**: return one `float` per name, in the given order.
  `Simulation` checks the length against `len(names)` and raises
  `SimulationError` on a mismatch.
* **`terminate`**: release the model. Always called from `run()`'s
  `finally` block, even after an exception from `initialize`, `advance`,
  `read`, or a sink/subscriber.

`Simulation.run()` drives a fixed grid from its own state
(`start`/`stop`/`step`, fixed at construction): it reads the sample at
`t = start` without calling `advance` (the model is already there right
after `initialize`), then repeatedly computes the next grid point
`t = start + i * step` and calls `advance(t)` followed by `read`. The final
communication point is clamped to `stop` exactly, even when
`stop - start` is not an integer multiple of `step`: a run with
`stop=1.0, step=0.4` visits `t = 0.0, 0.4, 0.8, 1.0` (three `advance()`
calls, not `0.0, 0.4, 0.8, 1.2`). The loop's continuation test
(`t < stop - eps`, with `eps = step * 1e-9`) guards against float
accumulation error in `start + i * step`, which could otherwise stop one
grid point short of `stop` or produce an extra point after it. `eps` is
relative to `step` rather than an absolute constant, so it scales with the
run's grid resolution.

A run of `n` communication steps therefore delivers `n + 1` samples;
`SimulationResult.steps` counts the `advance()` calls, not the samples.

The SDK ships three drivers. `OMSimulatorDriver(inst, system="default")`
drives an OMSimulator model the caller instantiated in this process
(requires the `sim` extra). `DockerOMSimulatorDriver` runs OMSimulator in
a container (section 2). `FunctionDriver` runs without a simulator.

`FunctionDriver(fn)` evaluates `fn(t)` at each communication point. `fn`
returns the observed values at time `t`, either as a sequence in the
observed-variable order the run was initialized with, or as a mapping
looked up by name:

```python
FunctionDriver(lambda t: [-4.6 + 1.3 * t, math.cos(2.0 * t)])
FunctionDriver(lambda t: {"speed": 2.0 * t, "torque": 1.0})
```

A mapping must cover every observed variable; a missing name raises
`SimulationError`, as does a sequence of the wrong length. `FunctionDriver`
needs no input files and no external processes, which makes it the usual
`fallback=` for `auto_driver` (section 3) and the backend for tests,
examples, and demos that do not need a simulator.

## 2. Stream protocol (`DockerOMSimulatorDriver`)

`DockerOMSimulatorDriver`, and any other out-of-process driver following
the same protocol, speaks to its simulation runner over the runner's
stdout, one line per communication step. The reference runner is
`docker/run_simulation.py`.

1. **Handshake.** A compliant runner must first print the literal line
   `#omuq-sim v1` (`omuq.drivers.HANDSHAKE`). The driver ignores stray
   output before the handshake (for example, a simulator's own startup
   logging on stdout); after the handshake, any output that is not a valid
   data line is a protocol violation. Three things can go wrong while
   waiting for the handshake, or for the initial sample read right after
   it, each raising `SimulationError` (see "stderr surfacing" below for
   what is and is not appended to each):
   * more than 200 lines arrive without one matching the handshake; only
     this case's message also quotes the first 5 of those lines;
   * the runner's stdout ends first: "the simulation runner ended before
     sending the handshake" (or "...initial sample"), with no lines quoted;
   * no line arrives within the per-line `timeout=` (60s default): "timed
     out waiting for the handshake" (or "...initial sample"), with no
     lines quoted either.
2. **Data lines.** Every line at and after the handshake, starting with
   the initial sample read immediately after it, is CSV: an absolute time
   followed by one value per observed variable, in the run's declared
   order (`t,v1,v2,...`). A line that does not parse as that shape (wrong
   field count, non-numeric field) raises `SimulationError` quoting the raw
   line.
3. **Time-grid divergence.** Each data line's time is compared against the
   time `Simulation` expected for that communication point (its own `t`,
   or `start` for the initial sample), within
   `max(1e-9, |expected| * 1e-9)`. A runner that reports a different time
   than the one it was told to `advance` to indicates a runner-side bug;
   the run aborts immediately with "container time grid diverged".
4. **stderr surfacing.** The subprocess's stderr is collected on a
   background thread for the whole run, not only at failure time. Its last
   10 lines are appended to the errors raised while waiting for or parsing
   runner output (the noise-budget, timeout, end-of-stream, and
   malformed-line cases, items 1 and 2 above), so a runner-side traceback
   appears next to the failure. It is not appended to the
   time-grid-divergence error (item 3) or to the API-misuse guards (e.g.
   calling `advance` before `initialize`).
5. **Shutdown.** `terminate()` asks the process to exit (`SIGTERM`), waits
   up to 5 seconds, then kills it.

A driver line is read with a per-line timeout (`timeout=`, 60s default);
container start-up under platform emulation (section 3) counts against the first
line's budget, so a slow-starting emulated container needs a longer
`timeout=`, not a longer per-step one.

## 3. Auto driver selection

`auto_driver(ssp_path, ...)` picks a backend automatically:

1. **`"local"`**: attempt `from OMSimulator import SSP`, then instantiate
   `ssp_path`. Succeeds only when OMSimulator's Python bindings are
   importable in the current interpreter (there are no macOS wheels, so
   this probe never succeeds there).
2. **`"docker"`**: check that the `docker` executable resolves on `PATH`
   (`shutil.which`), then that `docker image inspect <image>` succeeds for
   `image` (default `"omuq-omsimulator"`, the tag
   `docker build -t omuq-omsimulator docker/` produces; see
   `docker/README.md`). Neither check runs a container.

Probes run in `prefer` order (default `("local", "docker")`), and the first
one that succeeds is returned. If none does, `fallback` (any driver
object, typically a `FunctionDriver`) is returned when given, so a demo or
a test can still run on a machine with neither backend; otherwise
`DriverNotFoundError` is raised, naming each probe's failure reason and
how to fix it.

`platform="auto"` (the default, forwarded to `DockerOMSimulatorDriver`)
resolves to `"linux/amd64"` on an arm64/aarch64 host and to `None`
otherwise. OMSimulator publishes x86-64 wheels only, so Apple Silicon
hosts run the image under Docker's emulation layer while other platforms
run it natively. Pass an explicit string (or `None`) to override.

`auto_driver` is the only place in omuq-python that logs (`omuq.drivers`,
`INFO`); it reports which backend was selected.

## 4. Sinks

A sink receives every sample of a run through three lifecycle methods:

```python
class Sink(Protocol):
    def on_start(self, names: Sequence[str]) -> None: ...
    def on_sample(self, sample: Sample) -> None: ...
    def on_finish(self) -> None: ...
```

`Simulation.run()` calls `on_start` once (after `driver.initialize`, before
the first sample), `on_sample` once per delivered sample, and `on_finish`
exactly once from its `finally` block. `on_finish` must therefore tolerate
`on_start` never having run: if `driver.initialize()` itself raises, no
sink sees `on_start`, but every registered sink still gets `on_finish()`
during cleanup. `CsvSink` satisfies this by only closing a file it
actually opened; a custom sink that assumes `on_start` always precedes
`on_finish` will raise from cleanup and mask the real error.

A plain callable may be passed to `subscribe()` in place of a `Sink`; it is
wrapped to receive `on_sample` only (`on_start`/`on_finish` become no-ops).

**`CsvSink(path)`**: opens `path` in `on_start` and writes a header row
`time,<name>,...`; each sample is one more row, `time` then each observed
value in declared order. Uses `csv.writer` on a file opened with
`newline=""`, so lines end `\r\n`. This is the exact format
`omuq.samples_from_csv` reads back, and the format the write-back path
(`UqManager.record_result`, section 7) writes when it stores a run's samples.

**`PrintSink(every=1, precision=4, file=None)`**: prints one line per
`every`-th sample (`every=1` prints all samples), each value formatted to
`precision` significant digits, with a `[!domainId]` marker per domain the
sample fell outside. The throttle is a sample count and is not overridden
by violations: a violating sample between printed samples is not printed.
Subscribe with `on_violation` to observe every violation. `every < 1`
raises `SimulationError` at construction.

**`MemorySink()`**: keeps `.names` and every `.samples` of the latest run
in memory; `on_start` clears both, so one instance can be reused across
sequential runs without accumulating them. Domain fitting
(`fit_operational_domain(mem.samples, ...)`) and write-back
(`record_result(..., samples=mem.samples)`) both read from it; a run's
point cloud is `[s.values for s in mem.samples]`.

**Custom sinks** implement the `Sink` protocol directly (structurally, no
base class to inherit) or are passed as a plain callable to `subscribe`.

## 5. Domain monitoring semantics

`Simulation.monitor(domain, tol=1e-9)` checks every sample against one
domain's boundary; `Simulation.for_study` calls it for every domain the
study declares that this run can check (see "skipped domains" below).

**Counting model.** Each monitored domain keeps two independent counters,
both reported keyed by domain id (every monitored domain has an entry,
zeros included):

* **`samples_outside`**: how many samples, over the whole run, fell
  outside the boundary. A `DomainViolation` is emitted for each one.
* **`exits`**: how many excursions there were, that is, transitions from
  inside to outside. One long continuous excursion produces many
  `samples_outside` and one exit; repeated brief excursions produce many
  `exits` and few `samples_outside`.

**Tolerance.** Containment is checked with `tol=1e-9` by default, an
absolute margin: on a box, per axis bound; on a hull, a per-face offset
against Qhull's unit-normal halfspace equations. `Simulation.monitor`
accepts `tol=` to loosen or tighten it per domain.

**Caveat: zero-margin fitted domains.** A domain fitted by
`omuq.fitting.fit_boundary`/`fit_operational_domain`/`fit_activity_domain`
with `inflate=0.0` and no `pad` (the defaults) is only guaranteed to
contain its own input points up to that fit's quantization tolerance
(one formatting step of `precision`; see fitting.py's Precision section),
which is normally far looser than `monitor()`'s own default `tol=1e-9`.
Formatting a fitted boundary's coordinates to `precision` significant
digits can move a face by more than `1e-9`, so re-verifying a zero-margin
fit's own calibration data under `monitor()`/`for_study` can report a
handful of phantom `samples_outside`/`exits` even though the fit itself
raised no error. Give a zero-margin fit a small `pad=` (a box) or
`inflate=` (either shape) when it must stay violation-free against its own
data under later monitoring, or monitor it with a `tol=` at least as loose
as the fit's quantization step.

**Skipped domains (`for_study` only).** `for_study` builds one monitor per
domain it can, and records the rest in `skipped_domains` as
`SkippedDomain(domain_id, reason)` instead of failing the whole run over
one bad or unsupported domain:

* the domain has neither a `ConvexHull` nor a `HyperRectangle` boundary;
* the domain declares no `Axes`;
* one or more of the domain's axes is not an observed variable of this run
  (see "axis subsets" below);
* checking a `ConvexHull` boundary needs scipy, and this environment does
  not have it (`geometry.HullUnavailableError`; see the scipy policy
  below).

Everything else (too few points for the hull's dimension, coordinates
that do not parse, a degenerate collinear/coplanar point set Qhull itself
rejects) still raises `SimulationError` and aborts building the
`Simulation`, from `for_study` exactly as it would from a manual
`monitor()` call. `for_study` skips a domain only for environment
problems (a missing scipy install); an invalid point set would fail on
every machine and raises. Calling `monitor()` directly always raises on
both kinds of problem.

**Axis-subset rule.** A domain's `Axes` must all be observed variables of
the run being monitored, but the reverse is not required: a domain may
name a subset of the run's observed variables (a 3-variable run can still
be checked against a domain defined over just one of them). Different
domains of the same run may use different, overlapping, or disjoint axis
subsets.

**`on_violation(fn, only=None)`** subscribes `fn` to every `DomainViolation`
as it happens; `only` (a domain id, a kind such as `"Validation"`, or an
iterable of either) filters which ones reach `fn`. A filter that matches
none of the run's monitored domain ids or kinds raises a `UserWarning` at
`run()` time; without the warning, a filter that never matches would be
indistinguishable from a domain that was never violated.

## 6. Web UI architecture

`sim.watch()` (called before `run()`) constructs a `WebUi`, subscribes it
to the run as an ordinary `Sink`, starts a local HTTP server, and opens the
browser. Everything is stdlib (`http.server.ThreadingHTTPServer`); there is
no JavaScript build step and no external service. `WebUi` binds
`127.0.0.1` by default (override with `host=`) and an ephemeral port unless
`port=` is given.

**Event bus.** Samples become Server-Sent Events. A single `_EventBus`
keeps the complete history of every event published (as raw SSE frames)
alongside a live queue per connected client, all under one lock: publishing
appends to the history and pushes to every live queue in the same critical
section that subscribing replays the history into a new queue and
registers it live. A client therefore sees every frame exactly once, in
publish order, whether it connects before, during, or after any given
event.

**Endpoints:**

| Endpoint | Returns |
| --- | --- |
| `GET /` | the bundled single-page app (`index.html`) |
| `GET /static/plotly.min.js` | the vendored Plotly gl3d bundle (immutable cache) |
| `GET /api/init` | JSON run description: title, study name, observed names, `start`/`stop`/`step`, and the full domain inventory (every domain the study declares, monitored or not, with its axes, geometry, vertices, and, for a skipped one, why) |
| `GET /api/events` | `text/event-stream` of `status`/`sample`/`summary` events |

**Replay on connect.** Because the event bus keeps full history,
`/api/events` always starts by draining that history to a new client
before it joins the live stream: a page opened after the run finished, or
refreshed mid-run, sees the same sequence of events a client connected
from `t=0` would have. A `WebUi` serves exactly one run: it is constructed
fresh by each `sim.watch()` call and has nothing to replay for a later,
different run.

**Events.** `status` (`{"state": "waiting"|"running"|"finished"}`) brackets
the run; `sample` carries `t`, `values` (non-finite values become JSON
`null`), and any `violations` (`{"id", "kind"}` pairs) for that step;
`summary`, published once from `on_finish`, carries the final step and
sample counts, end time, and the same `samples_outside` counts
`SimulationResult` reports, keyed the same way. `on_finish` cannot
distinguish a clean finish from an exception during the run (both reach the
sink's `finally`-driven `on_finish`), so the page shows "finished" plus
whatever was streamed either way; success or failure is determined by the
caller's own exception handling, not by the UI.

**Heartbeat.** An idle connection (no event published for `heartbeat`
seconds, default 15.0) receives an SSE comment (`: keep-alive`) instead of
a real event, so the connection, and any proxy between browser and server,
does not time out while no samples arrive.

**Lifecycle.** `ui.wait()` (call after `run()`) prints the URL and blocks
until Ctrl+C, then closes the bus and shuts the server down; `WebUi` is
also a context manager. Calling `watch()` after `run()` has already started
raises `SimulationError`: the UI must be attached before the first sample
exists.

## 7. Results write-back walk-through

`pkg.uq.record_result(attached, result, *, activity=0, samples=None,
store_samples=True, summaries="auto", update=True)` is the runtime
counterpart to guideline section 6a ("Recording results back into a study" in
`docs/IMPLEMENTATION_GUIDELINE.md`). This section describes what it does;
the guideline states the normative rules.

**Metrics.** Every call writes one `Results` element holding:

* one `ErrorMetric` per monitored domain, with `type="DomainViolationCount"`,
  `name` = the domain's id, `value` = that domain's `samples_outside`
  count, `threshold="0.0"` (float-typed, so it serializes with the
  decimal), and `pass` = `value == 0`. The metrics are sorted by domain id
  (not by monitoring order), so the serialized document does not depend on
  the order the study lists its domains;
* one further `ErrorMetric`, `type="SampleCount"`, `value` = `steps + 1`
  (no `name`/`threshold`/`pass`).

**Sample table.** When `samples` is given (typically a `MemorySink`'s
`.samples`) and `store_samples` is not `False`, the run is also written as
a CSV entry under `resources/uq/`, in `CsvSink`'s exact byte format (section 4),
so `samples_from_csv` reads it back. The entry name is derived
from the study document's own file stem plus the activity's id (or
`activity<N>` when it has none), e.g.
`resources/uq/BatteryUQ-fuq1.results.csv`; `store_samples="name.csv"`
picks the name instead, but it must still resolve inside `resources/uq/`,
end in `.csv`, and name neither the reserved study-document suffix
(`.uq.xml`) nor the package entry of any study currently attached;
otherwise the call is rejected with `ModelError` rather than letting a
sample table overwrite a study document.
A second, otherwise-empty `Results` element is added alongside the metrics
one, pointing at the CSV with `source` (the relative path),
`type="text/csv"`, `checksum` (sha-256 of the exact bytes written), and
`checksumType="sha-256"`. This is the same `AExternalSource` convention
that guideline section 6 defines for any external omuq data, so
`validate(level=2)` verifies this checksum exactly as it would any other.

**Summaries.** `summaries="auto"` (the default) additionally writes a
`Normal(mu, sigma)` per observed variable, but only when `samples` were
given and the activity's `DesiredResults` asked for a `mean` or a
`standardDeviation`; `True` forces them (and raises if no `samples` were
passed); `False` always suppresses them. `sigma` is the population
standard deviation (`statistics.pstdev`): the samples are the entire run,
not a draw from it.

**Wholesale replacement.** `ResultsType` carries no id and no name in the
schema, so there is no way to recognize "the same result, written again"
and update it in place. `record_result` therefore owns the activity's
whole `ResultSet` and replaces it entirely on every call, rather than
accumulating near-duplicate `Results` elements across re-runs. Anything
hand-built there that must survive belongs in another activity, or must be
re-supplied after each recording. The CSV entry is replaced the same way
(same entry name, same archive position) rather than added again.

**Idempotency.** Recording the same `result`/`samples` twice is byte-stable
(besides `generationDateAndTime`, refreshed both times; see below) and
adds no new package entries: the second call's `RecordedResult` compares
equal to the first, and the archive still holds exactly one copy of the
sample-table entry. Everything that can be rejected (a bad
`store_samples=` name, an impossible `summaries=` choice, samples missing a
value `record_result` needs) is computed before any package entry is
touched, so a bad call cannot leave a half-recorded package (a CSV written
but its document not updated, or vice versa).

**Document write.** Unless `update=False`, `record_result` re-serializes
the whole study document into its package entry the same way
`UqManager.update` does (used directly when a caller adds a fitted domain
or a coverage judgment after recording; see below).
`generationDateAndTime` is refreshed unconditionally (guideline section 4.5:
writers SHOULD refresh it "when creating or modifying a document", and
this counts as a modification even on a byte-stable re-run), while
`generationTool` is only filled in when absent, so a document generated by
another tool keeps its original value. Both `record_result` and `update`
refuse a study stored as inline `ssc:MetaData/Content` (`LinkError`):
there is no package entry of its own to rewrite.

**Composing a full recording.** `record_result` only touches the
`ResultSet` and, optionally, a CSV entry. Fitting a realized domain from
the run and judging its coverage are separate, explicit steps that end
with one more `update()`:

```python
attached = pkg.uq.study(0)
pkg.uq.record_result(attached, result, samples=mem.samples)

envelope = fit_activity_domain(mem.samples, OBSERVED, id="runEnvelope", shape="box")
model.add_domain(attached.document, envelope)  # appended to Domains
model.upsert_coverage(
    attached.document,
    coverage_from_result(
        result,
        requested="domainOfValidation",
        realized="runEnvelope",
        when_violated="AcceptableRisk",
    ),
)
pkg.uq.update(attached)  # writes the domain + coverage too
```

**`coverage_from_result`** builds a `DomainCoverage` from a run's
recorded counts: `requested`/`realized` are the ids of the two domains
being compared (typically the domain that was monitored and one, like
`envelope` above, fitted to the run's samples); `domain_id=` picks which
`samples_outside` entry to read when neither of those two is itself the
monitored domain's id (default: `requested`). A clean run
(`samples_outside == 0`) is classified `when_clean` (default `"Covered"`)
automatically. A run that left the domain is not auto-classified: without
`when_violated`, `coverage_from_result` raises `ModelError`. The severity
of an excursion (`"HighRisk"`, `"AcceptableRisk"`, `"NotNeeded"`, or
`"Covered"`) must be supplied by the caller. The counts are written into
the coverage's `description` in either case. The default `id`
(`coverage-<requested>-<realized>`) is stable across re-runs, so passing
the result through `model.upsert_coverage` (as above) replaces the same
coverage record instead of accumulating duplicates.
