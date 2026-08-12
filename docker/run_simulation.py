#!/usr/bin/env python3
"""Stream an OMSimulator SSP simulation as CSV lines (omuq docker runner).

Protocol, consumed by ``omuq.DockerOMSimulatorDriver``:

  line 1:  ``#omuq-sim v1 names=<comma-separated names>``
  then:    one ``t,v1,v2,...`` line per communication step, over the same
           grid the host computes: t_i = start + i*step, with the final
           partial step clamped to stop.

Errors go to stderr, exit code 1.

The script depends only on the stdlib and OMSimulator, so the container
does not need omuq installed. It supports both OMSimulator python API
generations, since the shipped API depends on the installed version: the
v3 object API (SSP/instantiate/CRef) and the classic cref-string API
(OMSimulator()/importFile/getReal).
"""

import argparse
import os
import sys


def claim_stdout():
    """Reserve fd 1 for the protocol; OMSimulator's C prints go to stderr.

    libOMSimulator writes info/warning lines to fd 1, which would corrupt
    the sample stream. Duplicate the original stdout for protocol output
    and point fd 1 at stderr before OMSimulator is imported.
    """
    protocol = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    return protocol


def grid(start, stop, step):
    """Yield the communication grid, same rule as omuq.Simulation.run.

    The rule is duplicated from omuq.Simulation.run so the container and
    the host agree on the grid without sharing code.
    """
    eps = step * 1e-9
    t = start
    i = 0
    yield t
    while t < stop - eps:
        i += 1
        t = start + i * step
        if t > stop:
            t = stop
        yield t


def _check(status, what):
    """Raise for classic-API status codes worse than oms_status_warning."""
    if isinstance(status, int) and status > 1:
        raise RuntimeError(f"{what} failed with status {status}")


class V3Backend:
    """OMSimulator v3 object API: SSP -> instantiate -> stepUntil/getValue."""

    def __init__(self, ssp_path, system):
        from OMSimulator import SSP  # raises ImportError on classic-only installs

        try:
            from OMSimulator import CRef
        except ImportError:
            CRef = None
        self._CRef = CRef
        self._system = system
        self._inst = SSP(ssp_path).instantiate()

    def setup(self, start, stop, step):
        m = self._inst
        if start and hasattr(m, "setStartTime"):
            m.setStartTime(start)
        if hasattr(m, "setStopTime"):
            m.setStopTime(stop)
        for setter in ("setFixedStepSize", "setStepSize"):
            if hasattr(m, setter):
                getattr(m, setter)(step)
                break
        if hasattr(m, "stepUntil"):
            self._advance = m.stepUntil
        elif hasattr(m, "doStep"):
            self._advance = lambda t: m.doStep()
        else:
            attrs = ", ".join(sorted(a for a in dir(m) if not a.startswith("_")))
            raise RuntimeError(
                f"model has neither stepUntil nor doStep; attributes: {attrs}"
            )
        m.initialize()

    def cref(self, name):
        parts = name.split(".")
        if self._CRef is not None:
            return self._CRef(self._system, *parts)
        return ".".join([self._system, *parts])

    def advance(self, t):
        self._advance(t)

    def get(self, ref):
        return float(self._inst.getValue(ref))

    def close(self):
        for call in ("terminate", "delete"):
            if hasattr(self._inst, call):
                try:
                    getattr(self._inst, call)()
                except Exception:
                    pass


class ClassicBackend:
    """Classic OMSimulator API: cref strings like model.system.component.var."""

    def __init__(self, ssp_path, system):
        from OMSimulator import OMSimulator

        self._oms = OMSimulator()
        try:
            self._oms.setCommandLineOption("--suppressPath=true")
        except Exception:
            pass
        model, status = self._oms.importFile(ssp_path)
        _check(status, "importFile")
        self._model = model
        self._system = system

    def setup(self, start, stop, step):
        oms = self._oms
        if start:
            _check(oms.setStartTime(self._model, start), "setStartTime")
        _check(oms.setStopTime(self._model, stop), "setStopTime")
        try:
            oms.setFixedStepSize(f"{self._model}.{self._system}", step)
        except Exception:
            pass
        _check(oms.instantiate(self._model), "instantiate")
        _check(oms.initialize(self._model), "initialize")

    def cref(self, name):
        return f"{self._model}.{self._system}.{name}"

    def advance(self, t):
        _check(self._oms.stepUntil(self._model, t), "stepUntil")

    def get(self, ref):
        value, status = self._oms.getReal(ref)
        _check(status, f"getReal({ref})")
        return float(value)

    def close(self):
        for call in ("terminate", "delete"):
            try:
                getattr(self._oms, call)(self._model)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="omuq OMSimulator runner")
    parser.add_argument("--ssp", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--stop", type=float, required=True)
    parser.add_argument("--step", type=float, required=True)
    parser.add_argument("--system", default="default")
    parser.add_argument(
        "--names", required=True, help="comma-separated observed variable names"
    )
    args = parser.parse_args()
    names = [n for n in args.names.split(",") if n]
    if not names:
        print("omuq-sim runner error: no observed variable names", file=sys.stderr)
        return 1

    protocol = claim_stdout()
    backend = None
    try:
        try:
            backend = V3Backend(args.ssp, args.system)
        except ImportError:
            backend = ClassicBackend(args.ssp, args.system)
        backend.setup(args.start, args.stop, args.step)
        refs = [backend.cref(n) for n in names]
        print(f"#omuq-sim v1 names={','.join(names)}", file=protocol, flush=True)
        first = True
        for t in grid(args.start, args.stop, args.step):
            if not first:
                backend.advance(t)
            first = False
            values = [backend.get(r) for r in refs]
            print(
                ",".join([repr(t)] + [repr(v) for v in values]),
                file=protocol,
                flush=True,
            )
    except Exception as exc:
        print(f"omuq-sim runner error: {exc}", file=sys.stderr)
        return 1
    finally:
        if backend is not None:
            backend.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
