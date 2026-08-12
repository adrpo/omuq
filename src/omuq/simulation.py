"""Drive a simulator over an omuq study and stream the observed samples.

The SDK does not create simulators. The user configures one - an OMSimulator
model instantiated in-process, or OMSimulator inside a Docker container (see
:mod:`omuq.drivers`) - and passes a small driver object, or lets
:meth:`Simulation.from_package` pick one with :func:`omuq.auto_driver`.
:class:`Simulation` drives it over a fixed communication-step grid, reads the
observed variables declared in the omuq activity at every step, and pushes
each :class:`Sample` to subscribed callables and sinks such as
:class:`CsvSink`, :class:`PrintSink` and :class:`MemorySink`.

Domains declared in the study (typed operational domains and activity domains
such as the domain of validation) can be monitored: every sample is tested
against each monitored boundary and a :class:`DomainViolation` is emitted for
every point that falls outside, saying which boundary was left. Violation
subscribers can filter by domain id or kind, e.g. ``only="Validation"``.

There are three construction paths: :meth:`Simulation.for_activity` takes the observed
variables and the time grid from one activity, :meth:`Simulation.for_study`
adds the study's domains, and :meth:`Simulation.from_package` adds the SSP -
study selection, the SSD's ``DefaultExperiment``, and backend selection.
"""

from __future__ import annotations

import csv
import os
import warnings
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, Protocol

from . import geometry
from .drivers import auto_driver
from .errors import ModelError, SimulationError
from .model import (
    Activity,
    ActivityDomainType,
    HyperRectangleType,
    TypedOperationalDomainType,
    UncertaintyQuantification,
    activity_of,
    axis_names,
    domains_of,
    observed_names,
    shape_of,
)

if TYPE_CHECKING:
    # Annotation-only: both modules are imported inside the one method that
    # needs them (from_package, watch), so driving a simulation never pulls
    # in the package layer or the web server.
    from .package import SspPackage
    from .webui import WebUi

#: Kept as an internal alias: the helper now lives in :mod:`omuq.model`.
_observed_names = observed_names


def _kind_of(domain) -> str:
    """A domain's ``kind`` as a plain string.

    ``TypedOperationalDomain/@kind`` is an enumeration in the schema while
    ``ActivityDomain/@kind`` is a free string, and violation filters treat
    both the same way.
    """
    kind = domain.kind
    return kind.value if hasattr(kind, "value") else str(kind)


def _resolve_activity(
    study: UncertaintyQuantification, activity: int | str | Activity
) -> Activity:
    """The activity itself, or the one at an index / with an id or name."""
    if not isinstance(activity, (int, str)):
        return activity
    try:
        return activity_of(study, activity)
    except ModelError as exc:
        # Re-raise as SimulationError for simulation callers.
        raise SimulationError(str(exc)) from exc


@dataclass(frozen=True)
class DomainViolation:
    """One observed point falling outside one monitored domain boundary."""

    time: float
    domain_id: str
    domain_name: str | None
    domain_kind: str
    names: tuple[str, ...]
    point: tuple[float, ...]

    def __str__(self) -> str:
        coords = ", ".join(f"{v:g}" for v in self.point)
        return (
            f"t={self.time:g}: point ({coords}) outside "
            f"{self.domain_kind} domain {self.domain_id!r}"
        )


@dataclass(frozen=True)
class Sample:
    """One communication step: time plus name -> value in declaration order."""

    time: float
    values: dict[str, float]
    violations: tuple[DomainViolation, ...] = ()


class SkippedDomain(NamedTuple):
    """A domain :meth:`Simulation.for_study` could not monitor, and why.

    A named tuple; it unpacks and converts with ``dict()`` like a plain
    ``(id, reason)`` tuple.
    """

    domain_id: str
    reason: str


@dataclass(frozen=True)
class SimulationResult:
    """What a completed run observed (samples delivered = ``steps + 1``).

    ``samples_outside`` counts how many samples fell outside each monitored
    domain; ``exits`` counts inside-to-outside transitions. Both are keyed
    by domain id and carry an entry for every monitored domain, zeros
    included.

    ``violations`` is the complete event log in time order;
    :meth:`violations_of` filters it by the same rules as
    ``on_violation(only=...)``.
    """

    steps: int
    end_time: float
    names: tuple[str, ...]
    violations: tuple[DomainViolation, ...]
    samples_outside: dict[str, int]
    exits: dict[str, int]
    monitored_domains: tuple[str, ...]
    skipped_domains: tuple[SkippedDomain, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no monitored domain was ever left."""
        return not self.violations

    def violations_of(self, key: str | Iterable[str]) -> tuple[DomainViolation, ...]:
        """The violations of a domain id or kind, e.g. ``"Validation"``.

        Matches exactly like ``on_violation(only=...)``: one string or an
        iterable of strings, each tested against both the domain id and the
        domain kind.
        """
        keys = frozenset((key,)) if isinstance(key, str) else frozenset(key)
        return tuple(
            v for v in self.violations if v.domain_id in keys or v.domain_kind in keys
        )

    def summary(self) -> str:
        """Multi-line text summary: the grid, then one line per domain."""
        head = f"{self.steps} steps to t={self.end_time:g}"
        if not self.monitored_domains:
            head += " (no domains monitored)"
        lines = [head]
        for domain_id in self.monitored_domains:
            outside = self.samples_outside.get(domain_id, 0)
            if not outside:
                lines.append(f"  {domain_id}: inside throughout")
                continue
            excursions = self.exits.get(domain_id, 0)
            first = next(
                (v.time for v in self.violations if v.domain_id == domain_id), None
            )
            when = "" if first is None else f" (first exit t={first:g})"
            lines.append(
                f"  {domain_id}: {outside} samples outside in {excursions} "
                f"excursion{'' if excursions == 1 else 's'}{when}"
            )
        for domain_id, reason in self.skipped_domains:
            lines.append(f"  {domain_id}: not monitored ({reason})")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


class SimulationDriver(Protocol):
    """What a simulator backend must offer.

    Duck-typed: the runner calls these four methods and performs no
    isinstance checks. ``advance`` receives the absolute target time of the next
    communication point; all grid arithmetic stays in :class:`Simulation`.
    """

    def initialize(
        self, start: float, stop: float, step: float, names: Sequence[str]
    ) -> None: ...

    def advance(self, t: float) -> None: ...

    def read(self, names: Sequence[str]) -> list[float]: ...

    def terminate(self) -> None: ...


class Sink(Protocol):
    """Sample receiver with a run lifecycle.

    ``on_finish`` must tolerate being called when ``on_start`` never ran
    (early setup failure).
    """

    def on_start(self, names: Sequence[str]) -> None: ...

    def on_sample(self, sample: Sample) -> None: ...

    def on_finish(self) -> None: ...


class _CallableSink:
    """Adapt a plain callable to the Sink lifecycle."""

    def __init__(self, fn: Callable[[Sample], object]):
        self._fn = fn

    def on_start(self, names: Sequence[str]) -> None:
        pass

    def on_sample(self, sample: Sample) -> None:
        self._fn(sample)

    def on_finish(self) -> None:
        pass


class CsvSink:
    """Write samples to a CSV file: header ``time,<name>,...``, one row per step."""

    def __init__(self, path: str | os.PathLike):
        self._path = path
        self._file = None
        self._writer = None

    def on_start(self, names: Sequence[str]) -> None:
        self._file = open(self._path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(["time", *names])

    def on_sample(self, sample: Sample) -> None:
        self._writer.writerow([sample.time, *sample.values.values()])

    def on_finish(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
            self._writer = None


class MemorySink:
    """Keep the whole run in memory: the names, then every :class:`Sample`.

    The fitting and write-back steps read from this sink; a run's point
    cloud is ``[s.values for s in sink.samples]``. ``on_start`` clears the
    samples, so one sink can be reused across several runs without
    accumulating them.
    """

    def __init__(self):
        #: Observed-variable names of the latest run (``None`` before one).
        self.names: tuple[str, ...] | None = None
        #: Every sample of the latest run, in time order.
        self.samples: list[Sample] = []

    def on_start(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        self.samples.clear()

    def on_sample(self, sample: Sample) -> None:
        self.samples.append(sample)

    def on_finish(self) -> None:
        pass


class PrintSink:
    """Print every ``every``-th sample, marking the domains it fell outside::

        t=0.5  u3=-3.95, y2=0.351  [!domainOfValidation]

    ``every`` is a sample count (1 prints every sample). ``precision`` is
    the number of significant digits, and ``file`` defaults to stdout.
    Samples with violations are still subject to the throttle; subscribe
    with :meth:`Simulation.on_violation` to receive every violation.
    """

    def __init__(self, every: int = 1, *, precision: int = 4, file=None):
        if every < 1:
            raise SimulationError(
                f"PrintSink(every={every!r}): every is a sample count and must "
                "be at least 1"
            )
        self._every = int(every)
        self._precision = int(precision)
        self._file = file
        self._seen = 0

    def on_start(self, names: Sequence[str]) -> None:
        self._seen = 0

    def on_sample(self, sample: Sample) -> None:
        due = self._seen % self._every == 0
        self._seen += 1
        if not due:
            return
        digits = self._precision
        values = ", ".join(f"{n}={v:.{digits}g}" for n, v in sample.values.items())
        marks = "".join(f"  [!{v.domain_id}]" for v in sample.violations)
        print(f"t={sample.time:.{digits}g}  {values}{marks}", file=self._file)

    def on_finish(self) -> None:
        pass


@dataclass
class _Monitor:
    domain_id: str
    domain_name: str | None
    domain_kind: str
    names: tuple[str, ...]
    checker: geometry.RectChecker | geometry.HullChecker
    domain: TypedOperationalDomainType | ActivityDomainType | None = None
    #: Run statistics, folded in by :meth:`observe` (see SimulationResult).
    samples_outside: int = 0
    exits: int = 0
    outside: bool = False

    def observe(self, time: float, values: dict[str, float]) -> DomainViolation | None:
        """Test one sample against the boundary, updating the statistics.

        Only an inside -> outside transition increments the excursion
        count; each monitor tracks its own boundary state.
        """
        point = tuple(values[n] for n in self.names)
        if self.checker.contains(point):
            self.outside = False
            return None
        self.samples_outside += 1
        if not self.outside:
            self.exits += 1
            self.outside = True
        return DomainViolation(
            time=time,
            domain_id=self.domain_id,
            domain_name=self.domain_name,
            domain_kind=self.domain_kind,
            names=self.names,
            point=point,
        )


class Simulation:
    """Drive one simulation run over a fixed communication-step grid."""

    def __init__(
        self,
        driver: SimulationDriver,
        names: Sequence[str],
        *,
        stop: float,
        step: float,
        start: float = 0.0,
    ):
        names = tuple(names)
        if not names:
            raise SimulationError("no observed variable names given")
        if len(set(names)) != len(names):
            raise SimulationError("observed variable names contain duplicates")
        if step <= 0:
            raise SimulationError(f"step size must be positive, got {step}")
        if stop <= start:
            raise SimulationError(f"stop time {stop} must lie after start time {start}")
        self._driver = driver
        self._names = names
        self._start = float(start)
        self._stop = float(stop)
        self._step = float(step)
        self._sinks: list[Sink] = []
        self._monitors: list[_Monitor] = []
        self._violation_subs: list[
            tuple[Callable[[DomainViolation], object], frozenset[str] | None]
        ] = []
        self._ran = False
        self._study: UncertaintyQuantification | None = None
        #: Domains ``for_study`` could not monitor (see :class:`SkippedDomain`).
        self.skipped_domains: tuple[SkippedDomain, ...] = ()

    # -- construction ------------------------------------------------------

    @classmethod
    def for_activity(
        cls,
        activity: Activity,
        driver: SimulationDriver,
        *,
        step: float | None = None,
        stop: float | None = None,
        start: float = 0.0,
    ) -> Simulation:
        """Build a run from an omuq activity.

        Observed variables come from the activity; explicit ``step``/``stop``
        win over the activity's ``SimulationSetting`` (``interval`` and
        ``stopTime``).
        """
        setting = getattr(activity, "simulation_setting", None)
        if step is None:
            step = getattr(setting, "interval", None)
        if step is None:
            raise SimulationError(
                "no step size: pass step= or set SimulationSetting/@interval "
                "on the activity"
            )
        if stop is None:
            stop = getattr(setting, "stop_time", None)
        if stop is None:
            raise SimulationError(
                "no stop time: pass stop= or set SimulationSetting/@stopTime "
                "on the activity"
            )
        return cls(driver, _observed_names(activity), stop=stop, step=step, start=start)

    @classmethod
    def for_study(
        cls,
        study: UncertaintyQuantification,
        driver: SimulationDriver,
        *,
        activity: int | str | Activity = 0,
        step: float | None = None,
        stop: float | None = None,
        start: float = 0.0,
    ) -> Simulation:
        """Build a run from a study document and monitor its checkable domains.

        ``activity`` is a position, an id or name, or the activity object
        itself. Domains without a boundary, whose axes are not all observed
        variables of the run, or whose geometry this machine cannot check
        (a ConvexHull without scipy) are skipped and recorded in
        :attr:`skipped_domains`. Invalid geometry (too few hull points,
        degenerate point sets, unparsable coordinates) raises instead of
        being skipped.
        """
        act = _resolve_activity(study, activity)
        sim = cls.for_activity(act, driver, step=step, stop=stop, start=start)

        skipped: list[SkippedDomain] = []
        for domain in domains_of(study):
            if shape_of(domain) is None:
                skipped.append(
                    SkippedDomain(domain.id, "no ConvexHull/HyperRectangle boundary")
                )
                continue
            names = axis_names(domain)
            if not names:
                skipped.append(SkippedDomain(domain.id, "no axes declared"))
                continue
            missing = [n for n in names if n not in sim._names]
            if missing:
                skipped.append(
                    SkippedDomain(
                        domain.id,
                        "axes are not observed variables of this run: "
                        + ", ".join(missing),
                    )
                )
                continue
            try:
                sim.monitor(domain)
            except geometry.HullUnavailableError as exc:
                skipped.append(SkippedDomain(domain.id, str(exc)))
        sim.skipped_domains = tuple(skipped)
        sim._study = study
        return sim

    @classmethod
    def from_package(
        cls,
        package: str | os.PathLike[str] | SspPackage,
        *,
        study: int | str = 0,
        activity: int | str = 0,
        driver: SimulationDriver | None = None,
        fallback_driver: SimulationDriver | None = None,
        step: float | None = None,
        stop: float | None = None,
        start: float | None = None,
    ) -> Simulation:
        """Build a run from an SSP package.

        Opens ``package`` (a path or an already-open
        :class:`~omuq.SspPackage`), takes the attached ``study`` and its
        ``activity`` (both by position, id or name), monitors the study's
        domains as :meth:`for_study` does, and - unless ``driver`` is given
        - selects a backend with :func:`omuq.auto_driver`, falling back to
        ``fallback_driver`` when the machine has neither OMSimulator nor the
        docker image.

        The time grid is taken from the most specific source that has it:

        * ``step``: the argument, else ``SimulationSetting/@interval``;
        * ``stop``: the argument, else ``SimulationSetting/@stopTime``, else
          the SSD's ``DefaultExperiment/@stopTime``;
        * ``start``: the argument, else ``DefaultExperiment/@startTime``,
          else ``0.0``.

        SSP's ``DefaultExperiment`` carries no step size (SSP 2.0, chapter
        5), so a study whose activity declares no ``interval`` must be given
        one here.
        """
        from .package import SspPackage

        pkg = package if isinstance(package, SspPackage) else SspPackage.open(package)
        if not pkg.uq.studies():
            raise SimulationError(
                f"no omuq study is attached to {pkg.path or 'this package'}; "
                "attach one with pkg.uq.attach(study, anchor) before simulating"
            )
        attached = pkg.uq.study(study)
        act = _resolve_activity(attached.document, activity)
        setting = getattr(act, "simulation_setting", None)
        experiment = pkg.ssd().default_experiment
        where = f"study {attached.name!r}"

        if step is None:
            step = getattr(setting, "interval", None)
        if step is None:
            raise SimulationError(
                f"{where}: no step size; pass step= or set "
                "SimulationSetting/@interval on the activity (SSP's "
                "DefaultExperiment has no step size to fall back on)"
            )
        if stop is None:
            stop = getattr(setting, "stop_time", None)
        if stop is None and experiment is not None:
            stop = experiment.stop_time
        if stop is None:
            raise SimulationError(
                f"{where}: no stop time; pass stop=, set "
                "SimulationSetting/@stopTime on the activity, or set "
                "DefaultExperiment/@stopTime in the SSD"
            )
        if start is None and experiment is not None:
            start = experiment.start_time
        if start is None:
            start = 0.0

        if driver is None:
            if pkg.path is None:
                raise SimulationError(
                    "this package was opened from a file object, so there is "
                    "no SSP path to hand to a simulator; pass driver= (or "
                    "open the package from a path)"
                )
            driver = auto_driver(
                pkg.path, system=pkg.ssd().system_name, fallback=fallback_driver
            )
        return cls.for_study(
            attached.document, driver, activity=act, step=step, stop=stop, start=start
        )

    # -- configuration -----------------------------------------------------

    def monitor(
        self,
        domain: TypedOperationalDomainType | ActivityDomainType,
        *,
        tol: float = 1e-9,
    ) -> None:
        """Check every sample against ``domain``'s boundary during :meth:`run`."""
        if self._ran:
            raise SimulationError("cannot monitor a domain after the run")
        where = domain.id
        names = axis_names(domain)
        if not names:
            raise SimulationError(f"domain {where!r} declares no Axes")
        missing = [n for n in names if n not in self._names]
        if missing:
            raise SimulationError(
                f"domain {where!r} uses axes that are not observed variables "
                f"of this run: {', '.join(missing)}"
            )
        checker = geometry.checker_for_boundary(
            domain.boundary, len(names), where=where, tol=tol
        )
        self._monitors.append(
            _Monitor(
                domain_id=where,
                domain_name=domain.name,
                domain_kind=_kind_of(domain),
                names=names,
                checker=checker,
                domain=domain,
            )
        )

    def subscribe(self, subscriber: Sink | Callable[[Sample], object]) -> None:
        """Register a per-sample receiver: a callable or a Sink-like object."""
        if hasattr(subscriber, "on_sample"):
            self._sinks.append(subscriber)
        elif callable(subscriber):
            self._sinks.append(_CallableSink(subscriber))
        else:
            raise TypeError(
                f"{type(subscriber).__name__} is neither callable nor a sink "
                "with an on_sample method"
            )

    def on_violation(
        self,
        fn: Callable[[DomainViolation], object],
        *,
        only: str | Iterable[str] | None = None,
    ) -> None:
        """Call ``fn`` for every :class:`DomainViolation`.

        ``only`` filters by domain id or kind - a single string or an
        iterable of strings, e.g. ``only="Validation"`` to be notified only
        when the domain of validation is left.
        """
        if only is None:
            keys = None
        elif isinstance(only, str):
            keys = frozenset((only,))
        else:
            keys = frozenset(only)
        self._violation_subs.append((fn, keys))

    def watch(
        self,
        *,
        port: int = 0,
        host: str = "127.0.0.1",
        open_browser: bool = True,
        title: str | None = None,
    ) -> WebUi:
        """Open a live web view of this run in the browser.

        Starts a local server (bound to ``host``, 127.0.0.1 by default) that
        streams this simulation's samples, domains, and violations into a web
        page; the browser is opened right away. Must be called before
        :meth:`run`. Call ``wait()`` on the returned handle after the run to
        keep the page alive until Ctrl+C; late-opening or refreshed pages
        replay the entire run.
        """
        if self._ran:
            raise SimulationError("watch() must be called before run()")
        from . import webui

        ui = webui.WebUi(
            names=self._names,
            start=self._start,
            stop=self._stop,
            step=self._step,
            domains=self._domain_inventory(),
            study=self._study.name if self._study is not None else None,
            title=title or "omuq live simulation",
            host=host,
            port=port,
            open_browser=open_browser,
        )
        self.subscribe(ui)
        return ui

    def _domain_inventory(self) -> list[dict]:
        """Plain-dict description of the run's domains for the web UI."""
        monitored = {m.domain_id for m in self._monitors}
        reasons = dict(self.skipped_domains)

        def entry(domain) -> dict:
            shape = shape_of(domain)
            geom = None
            vertices: list[list[float]] = []
            if shape is not None:
                geom = "rect" if isinstance(shape, HyperRectangleType) else "hull"
                try:
                    vertices = [
                        list(p)
                        for p in geometry.parse_points(shape.point, where=domain.id)
                    ]
                except SimulationError:
                    if domain.id in monitored:
                        raise
                    vertices = []
            return {
                "id": domain.id,
                "name": domain.name,
                "kind": _kind_of(domain),
                "monitored": domain.id in monitored,
                "reason": reasons.get(domain.id),
                "geometry": geom,
                "axes": list(axis_names(domain)),
                "vertices": vertices,
            }

        # If the study has no Domains element, build the inventory from
        # the monitors (the case for manually monitored runs).
        if self._study is not None and self._study.domains is not None:
            return [entry(d) for d in domains_of(self._study)]
        inventory: list[dict] = []
        for monitor in self._monitors:
            if monitor.domain is not None:
                inventory.append(entry(monitor.domain))
            else:
                inventory.append(
                    {
                        "id": monitor.domain_id,
                        "name": monitor.domain_name,
                        "kind": monitor.domain_kind,
                        "monitored": True,
                        "reason": None,
                        "geometry": None,
                        "axes": list(monitor.names),
                        "vertices": [],
                    }
                )
        return inventory

    # -- execution ---------------------------------------------------------

    def run(self) -> SimulationResult:
        """Execute the run; always terminates the driver and finishes sinks."""
        if self._ran:
            raise SimulationError("this Simulation has already run; create a new one")
        self._ran = True
        self._warn_about_dead_filters()
        events: list[DomainViolation] = []
        ok = False
        deferred: list[Exception] = []
        i = 0
        t = self._start
        try:
            self._driver.initialize(self._start, self._stop, self._step, self._names)
            for sink in self._sinks:
                sink.on_start(self._names)
            self._emit(t, events)
            eps = self._step * 1e-9
            while t < self._stop - eps:
                i += 1
                t = self._start + i * self._step
                if t > self._stop:
                    t = self._stop
                self._driver.advance(t)
                self._emit(t, events)
            ok = True
            return SimulationResult(
                steps=i,
                end_time=t,
                names=self._names,
                violations=tuple(events),
                samples_outside={
                    m.domain_id: m.samples_outside for m in self._monitors
                },
                exits={m.domain_id: m.exits for m in self._monitors},
                monitored_domains=tuple(m.domain_id for m in self._monitors),
                skipped_domains=self.skipped_domains,
            )
        finally:
            # Always release the driver and close the sinks, without masking
            # an in-flight exception; on clean success, cleanup errors do raise.
            try:
                self._driver.terminate()
            except Exception as exc:
                deferred.append(exc)
            for sink in self._sinks:
                try:
                    sink.on_finish()
                except Exception as exc:
                    deferred.append(exc)
            if ok and deferred:
                raise deferred[0]

    def _warn_about_dead_filters(self) -> None:
        """Warn about ``on_violation(only=...)`` filters that cannot ever fire.

        A mistyped domain id would otherwise disable the subscriber
        silently. An empty filter (``only=[]``) also matches nothing, so
        the test is ``keys is not None`` rather than the truthiness of the
        set.
        """
        known = {m.domain_id for m in self._monitors}
        known |= {m.domain_kind for m in self._monitors}
        for _fn, keys in self._violation_subs:
            if keys is not None and not (keys & known):
                asked = ", ".join(sorted(repr(k) for k in keys))
                available = ", ".join(sorted(repr(k) for k in known)) or "none"
                warnings.warn(
                    f"on_violation(only=[{asked}]) matches no monitored "
                    f"domain, so that subscriber will never be called; this "
                    f"run monitors the ids and kinds {available}",
                    UserWarning,
                    stacklevel=3,
                )

    def _emit(self, t: float, events: list[DomainViolation]) -> None:
        raw = list(self._driver.read(self._names))
        if len(raw) != len(self._names):
            raise SimulationError(
                f"driver returned {len(raw)} value(s) for "
                f"{len(self._names)} observed variable(s)"
            )
        values = {n: float(v) for n, v in zip(self._names, raw, strict=False)}
        violations: list[DomainViolation] = []
        for monitor in self._monitors:
            violation = monitor.observe(t, values)
            if violation is not None:
                violations.append(violation)
        events.extend(violations)
        sample = Sample(time=t, values=values, violations=tuple(violations))
        for sink in self._sinks:
            sink.on_sample(sample)
        for fn, keys in self._violation_subs:
            for violation in violations:
                if (
                    keys is None
                    or violation.domain_id in keys
                    or violation.domain_kind in keys
                ):
                    fn(violation)
