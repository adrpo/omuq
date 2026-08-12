"""Simulator drivers for :class:`omuq.Simulation`.

Every driver here speaks the duck-typed :class:`omuq.SimulationDriver`
protocol. :class:`OMSimulatorDriver` wraps an OMSimulator model the user
instantiated in-process; :class:`DockerOMSimulatorDriver` runs OMSimulator
inside a Docker container (the only option on macOS, where OMSimulator has
no build) and streams one line per communication step out of the container,
so subscribers, CSV sinks, and domain monitoring behave identically to an
in-process run; :class:`FunctionDriver` computes the observed variables from
a function of time, for demos and tests that need no simulator at all.

:func:`auto_driver` picks between the two real backends by probing the
machine. The chosen backend is logged to the ``omuq.drivers`` logger at
INFO.
"""

from __future__ import annotations

import logging
import os
import platform as platform_module
import queue
import shutil
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import DriverNotFoundError, SimulationError

if TYPE_CHECKING:  # omuq.simulation imports this module at runtime
    from .simulation import SimulationDriver

#: First line every simulation runner must print (see docker/run_simulation.py).
HANDSHAKE = "#omuq-sim v1"

#: Logger used by :func:`auto_driver` to report the selected backend.
log = logging.getLogger("omuq.drivers")


class OMSimulatorDriver:
    """Drive an OMSimulator (v3 object API) model the user instantiated.

    The caller creates and keeps ownership of the model::

        from OMSimulator import SSP
        inst = SSP("model.ssp").instantiate()
        driver = OMSimulatorDriver(inst, system="default")

    Variables are addressed as ``CRef(system, *name.split("."))``. SSP allows
    literal dots inside element names; for such models pass ``cref_factory``,
    a callable mapping an observed-variable name to whatever the model's
    ``getValue`` accepts.
    """

    def __init__(
        self,
        instantiated_model,
        *,
        system: str = "default",
        cref_factory: Callable[[str], object] | None = None,
    ):
        self._model = instantiated_model
        self._system = system
        self._cref_factory = cref_factory
        self._crefs: dict[str, object] = {}
        self._mode: str | None = None

    def initialize(
        self, start: float, stop: float, step: float, names: Sequence[str]
    ) -> None:
        model = self._model
        if start != 0.0:
            if hasattr(model, "setStartTime"):
                model.setStartTime(start)
            else:
                raise SimulationError(
                    "this OMSimulator model offers no setStartTime; "
                    "only start=0.0 is supported"
                )
        if hasattr(model, "setStopTime"):
            model.setStopTime(stop)
        for setter in ("setFixedStepSize", "setStepSize"):
            if hasattr(model, setter):
                getattr(model, setter)(step)
                break
        if hasattr(model, "stepUntil"):
            self._mode = "stepUntil"
        elif hasattr(model, "doStep"):
            # Assumes the master's internal step equals the communication
            # step (we attempted to set it above).
            self._mode = "doStep"
        else:
            public = ", ".join(sorted(a for a in dir(model) if not a.startswith("_")))
            raise SimulationError(
                "the OMSimulator model offers neither stepUntil nor doStep; "
                f"available attributes: {public}"
            )
        for name in names:
            self._cref(name)
        model.initialize()

    def advance(self, t: float) -> None:
        if self._mode is None:
            raise SimulationError("driver not initialized")
        if self._mode == "stepUntil":
            self._model.stepUntil(t)
        else:
            self._model.doStep()

    def read(self, names: Sequence[str]) -> list[float]:
        return [float(self._model.getValue(self._cref(n))) for n in names]

    def terminate(self) -> None:
        # Never delete(): the user instantiated the model and keeps ownership.
        if hasattr(self._model, "terminate"):
            self._model.terminate()

    def _cref(self, name: str):
        if name in self._crefs:
            return self._crefs[name]
        if self._cref_factory is not None:
            ref = self._cref_factory(name)
        else:
            try:
                from OMSimulator import CRef
            except ImportError as exc:
                raise SimulationError(
                    "OMSimulator is not installed; install it or pass "
                    "cref_factory= to OMSimulatorDriver"
                ) from exc
            ref = CRef(self._system, *name.split("."))
        self._crefs[name] = ref
        return ref


class DockerOMSimulatorDriver:
    """Run the simulation inside a Docker container with OMSimulator.

    Spawns ``docker run`` on the image built from ``docker/Dockerfile`` and
    reads one CSV line per communication step from the container's stdout
    (protocol implemented by ``docker/run_simulation.py``). The directory
    containing ``ssp_path`` is mounted read-only at ``/data``.

    ``platform`` is forwarded as ``docker run --platform ...`` - use
    ``"linux/amd64"`` on Apple Silicon, since OMSimulator ships x86-64 wheels
    only. ``command`` replaces the whole ``docker run ...`` argv prefix and
    receives the job arguments with the host-side SSP path appended (used by
    the tests to exercise the stream protocol without docker). ``timeout``
    is the per-line wait in seconds; container start-up under emulation
    counts against the first line.
    """

    def __init__(
        self,
        ssp_path,
        *,
        image: str = "omuq-omsimulator",
        system: str = "default",
        platform: str | None = None,
        docker: str = "docker",
        command: Sequence[str] | None = None,
        timeout: float = 60.0,
    ):
        self._ssp = Path(ssp_path)
        self._image = image
        self._system = system
        self._platform = platform
        self._docker = docker
        self._command = list(command) if command is not None else None
        self._timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue | None = None
        self._stderr: list[str] = []
        self._last: list[float] | None = None
        #: argv of the spawned process (set by initialize; for inspection).
        self.argv: list[str] | None = None

    # -- SimulationDriver protocol ----------------------------------------

    def initialize(
        self, start: float, stop: float, step: float, names: Sequence[str]
    ) -> None:
        if not self._ssp.is_file():
            raise SimulationError(f"SSP file not found: {self._ssp}")
        ssp_arg = (
            str(self._ssp) if self._command is not None else f"/data/{self._ssp.name}"
        )
        job = [
            "--ssp",
            ssp_arg,
            "--start",
            repr(float(start)),
            "--stop",
            repr(float(stop)),
            "--step",
            repr(float(step)),
            "--system",
            self._system,
            "--names",
            ",".join(names),
        ]
        if self._command is not None:
            argv = [*self._command, *job]
        else:
            argv = [self._docker, "run", "--rm", "-i"]
            if self._platform:
                argv += ["--platform", self._platform]
            argv += ["-v", f"{self._ssp.parent.resolve()}:/data:ro", self._image]
            argv += job
        self.argv = argv
        try:
            self._proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise SimulationError(f"cannot start {argv[0]!r}: {exc}") from exc
        self._lines = queue.Queue()
        threading.Thread(
            target=self._pump_out, args=(self._proc.stdout,), daemon=True
        ).start()
        threading.Thread(
            target=self._pump_err, args=(self._proc.stderr,), daemon=True
        ).start()
        # Tolerate stray pre-handshake output (e.g. simulator logging that
        # escaped to stdout); data lines only ever follow the handshake.
        noise: list[str] = []
        while True:
            line = self._next_line("handshake")
            if line.startswith(HANDSHAKE):
                break
            noise.append(line)
            if len(noise) > 200:
                preview = "\n".join(noise[:5])
                raise SimulationError(
                    f"no {HANDSHAKE!r} handshake from the simulation runner; "
                    f"output began with:\n{preview}{self._stderr_tail()}"
                )
        self._consume_line(start, "initial sample")

    def advance(self, t: float) -> None:
        if self._proc is None:
            raise SimulationError("driver not initialized")
        self._consume_line(t, f"sample at t={t:g}")

    def read(self, names: Sequence[str]) -> list[float]:
        if self._last is None:
            raise SimulationError("driver not initialized")
        if len(self._last) != len(names):
            raise SimulationError(
                f"the simulation runner sent {len(self._last)} value(s) for "
                f"{len(names)} observed variable(s)"
            )
        return list(self._last)

    def terminate(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    # -- stream handling ---------------------------------------------------

    def _pump_out(self, stream) -> None:
        try:
            for line in stream:
                self._lines.put(line.rstrip("\n"))
        finally:
            self._lines.put(None)

    def _pump_err(self, stream) -> None:
        for line in stream:
            self._stderr.append(line.rstrip("\n"))

    def _next_line(self, what: str) -> str:
        try:
            line = self._lines.get(timeout=self._timeout)
        except queue.Empty:
            raise SimulationError(
                f"timed out waiting for the {what} from the simulation "
                f"runner{self._stderr_tail()}"
            ) from None
        if line is None:
            raise SimulationError(
                f"the simulation runner ended before sending the "
                f"{what}{self._stderr_tail()}"
            )
        return line

    def _consume_line(self, expected_t: float, what: str) -> None:
        line = self._next_line(what)
        parts = line.split(",")
        try:
            t = float(parts[0])
            values = [float(p) for p in parts[1:]]
        except ValueError:
            raise SimulationError(
                f"malformed line from the simulation runner: "
                f"{line!r}{self._stderr_tail()}"
            ) from None
        if abs(t - expected_t) > max(1e-9, abs(expected_t) * 1e-9):
            raise SimulationError(
                f"container time grid diverged: expected t={expected_t!r}, got t={t!r}"
            )
        self._last = values

    def _stderr_tail(self) -> str:
        if not self._stderr:
            return ""
        tail = "\n".join(self._stderr[-10:])
        return f"\nrunner stderr:\n{tail}"


class FunctionDriver:
    """Drive a run from a plain function of time, without a simulator.

    ``fn(t)`` returns the observed values at time ``t``, either as a
    sequence in the observed-variable order the run was initialized with,
    or as a mapping looked up by name::

        FunctionDriver(lambda t: [-4.6 + 1.3 * t, math.cos(2.0 * t)])
        FunctionDriver(lambda t: {"speed": 2.0 * t, "torque": 1.0})

    Deterministic and dependency-free. Suitable as the ``fallback=`` of
    :func:`auto_driver` and in demos and tests that do not need a
    simulator.
    """

    def __init__(self, fn: Callable[[float], Sequence[float] | Mapping[str, float]]):
        self._fn = fn
        self._names: tuple[str, ...] = ()
        self._t: float | None = None

    def initialize(
        self, start: float, stop: float, step: float, names: Sequence[str]
    ) -> None:
        self._names = tuple(names)
        self._t = float(start)

    def advance(self, t: float) -> None:
        self._t = float(t)

    def read(self, names: Sequence[str]) -> list[float]:
        if self._t is None:
            raise SimulationError("driver not initialized")
        values = self._fn(self._t)
        if isinstance(values, Mapping):
            missing = [n for n in names if n not in values]
            if missing:
                raise SimulationError(
                    f"the driver function returned no value for "
                    f"{', '.join(repr(n) for n in missing)} at t={self._t:g}; "
                    f"its mapping must cover every observed variable "
                    f"({', '.join(names)})"
                )
            return [float(values[n]) for n in names]
        row = [float(v) for v in values]
        if len(row) != len(names):
            raise SimulationError(
                f"the driver function returned {len(row)} value(s) at "
                f"t={self._t:g} for {len(names)} observed variable(s); a "
                f"sequence must follow the observed order ({', '.join(names)}), "
                "or return a mapping keyed by name"
            )
        return row

    def terminate(self) -> None:
        pass


# -- backend selection -----------------------------------------------------


def auto_driver(
    ssp_path: str | os.PathLike[str],
    *,
    system: str = "default",
    image: str = "omuq-omsimulator",
    docker: str = "docker",
    platform: str | None = "auto",
    prefer: Sequence[str] = ("local", "docker"),
    fallback: SimulationDriver | None = None,
    timeout: float = 60.0,
) -> SimulationDriver:
    """Return the best simulator backend this machine can run ``ssp_path`` with.

    Probes in ``prefer`` order: ``"local"`` imports OMSimulator and
    instantiates the SSP in-process; ``"docker"`` checks that the ``docker``
    executable exists and that ``image`` is present locally. The chosen
    backend is logged to ``omuq.drivers`` at INFO.

    When no probe succeeds, ``fallback`` (any driver object, e.g. a
    :class:`FunctionDriver`) is returned if given, and otherwise
    :class:`~omuq.errors.DriverNotFoundError` is raised naming every probe
    that failed and how to fix it.

    ``platform="auto"`` resolves to ``"linux/amd64"`` on arm64 hosts, where
    OMSimulator has x86-64 wheels only; an explicit string or ``None`` is
    passed to :class:`DockerOMSimulatorDriver` unchanged.
    """
    path = Path(ssp_path)
    failures: list[str] = []
    for probe in prefer:
        if probe == "local":
            driver = _local_driver(path, system, failures)
        elif probe == "docker":
            driver = _docker_driver(
                path,
                system=system,
                image=image,
                docker=docker,
                platform=platform,
                timeout=timeout,
                failures=failures,
            )
        else:
            raise SimulationError(
                f"unknown driver probe {probe!r} in prefer={tuple(prefer)!r}; "
                "expected 'local' and/or 'docker'"
            )
        if driver is not None:
            return driver
    if fallback is not None:
        log.info(
            "driver: %s supplied as fallback (%s)",
            type(fallback).__name__,
            "; ".join(failures),
        )
        return fallback
    raise DriverNotFoundError(
        f"no simulator backend can run {path}:\n  - "
        + "\n  - ".join(failures)
        + "\nPass an explicit driver=, or fallback= a stand-in such as "
        "FunctionDriver(lambda t: ...)"
    )


def _local_driver(
    path: Path, system: str, failures: list[str]
) -> SimulationDriver | None:
    try:
        from OMSimulator import SSP
    except ImportError:
        failures.append(
            "OMSimulator is not importable in this interpreter "
            "(fix: pip install OMSimulator)"
        )
        return None
    log.info("driver: in-process OMSimulator on %s (system %r)", path, system)
    return OMSimulatorDriver(SSP(str(path)).instantiate(), system=system)


def _docker_driver(
    path: Path,
    *,
    system: str,
    image: str,
    docker: str,
    platform: str | None,
    timeout: float,
    failures: list[str],
) -> SimulationDriver | None:
    executable = shutil.which(docker)
    if executable is None:
        failures.append(
            f"the {docker!r} executable is not on PATH (fix: install Docker, "
            f"then build the image from docker/ - see docker/README.md)"
        )
        return None
    probe = subprocess.run([executable, "image", "inspect", image], capture_output=True)
    if probe.returncode != 0:
        failures.append(
            f"docker has no local image {image!r} "
            f"(fix: docker build -t {image} docker/)"
        )
        return None
    resolved = _resolve_platform(platform)
    log.info(
        "driver: OMSimulator in docker image %r%s",
        image,
        f" (--platform {resolved})" if resolved else "",
    )
    return DockerOMSimulatorDriver(
        path,
        image=image,
        system=system,
        platform=resolved,
        docker=executable,
        timeout=timeout,
    )


def _resolve_platform(platform: str | None) -> str | None:
    if platform != "auto":
        return platform
    # OMSimulator publishes x86-64 wheels only, so an arm64 host must ask
    # docker for emulation explicitly.
    return "linux/amd64" if platform_module.machine() in ("arm64", "aarch64") else None
