"""Command line interface: ``omuq list|validate|run <package.ssp>``.

Also reachable as ``python -m omuq``, which is how front ends such as
OMEdit call it: they only need the path of a Python interpreter that has
omuq-python (and OMSimulator) installed.

Every command prints human-readable text by default and machine-readable
output with ``--json``:

* ``list`` and ``validate`` print one JSON document;
* ``run`` prints JSON lines, one event per line, flushed as they happen::

    {"event": "start", "study": ..., "names": [...], "domains": [...], ...}
    {"event": "sample", "time": 0.01, "values": [...], "outside": ["dov"]}
    {"event": "exit", "time": 1.01, "domain": "dov", "kind": ..., "point": [...]}
    {"event": "summary", "steps": 1000, "ok": false, "exits": {...}, ...}
    {"event": "artifacts", "csv": "...", "results": "..."}

  A failure is reported as ``{"event": "error", "message": ...}`` with exit
  status 1. ``sample`` events honour ``--every``; ``exit`` events are only
  emitted for inside-to-outside transitions, not for every sample outside.

In ``--json`` mode anything else written to standard output - for example
by the simulator's native code - is redirected to standard error, so
standard output carries the JSON events only.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import logging
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from . import model
from .constants import TOOL_VERSION
from .errors import OmuqError

#: Version of the JSON event and document format printed with ``--json``.
JSON_FORMAT_VERSION = 1


def _key(value: str | None) -> int | str:
    """A study/activity selector: a position when it is a number, else a name."""
    if value is None:
        return 0
    return int(value) if value.lstrip("-").isdigit() else value


def _kind(obj) -> str:
    kind = getattr(obj, "kind", None)
    return kind.value if hasattr(kind, "value") else str(kind)


def _activity_type(activity) -> str:
    """The activity's element name in the omuq schema, e.g. ``Validation``."""
    for field in dataclasses.fields(model.ActivitiesType):
        for choice in field.metadata.get("choices", ()):
            if choice["type"] is type(activity):
                return choice["name"]
    return type(activity).__name__.removesuffix("Type")


def _activity_info(index: int, activity) -> dict:
    setting = getattr(activity, "simulation_setting", None)
    try:
        observed = list(model.observed_names(activity))
    except OmuqError:
        observed = []
    return {
        "index": index,
        "id": activity.id,
        "name": getattr(activity, "name", None),
        "type": _activity_type(activity),
        "observed": observed,
        "stopTime": getattr(setting, "stop_time", None),
        "interval": getattr(setting, "interval", None),
        "results": len(model.results_of(activity)),
    }


def _domain_info(domain) -> dict:
    shape = model.shape_of(domain)
    return {
        "id": domain.id,
        "name": domain.name,
        "kind": _kind(domain),
        "geometry": None
        if shape is None
        else type(shape).__name__.removesuffix("Type"),
        "axes": list(model.axis_names(domain)),
    }


def describe_package(path: str | os.PathLike[str]) -> dict:
    """The package's studies, activities and domains as plain data."""
    from .package import SspPackage

    pkg = SspPackage.open(path)
    ssd = pkg.ssd()
    experiment = ssd.default_experiment
    return {
        "format": JSON_FORMAT_VERSION,
        "omuq": TOOL_VERSION,
        "package": str(Path(path).resolve()),
        "system": ssd.system_name,
        "defaultExperiment": None
        if experiment is None
        else {"startTime": experiment.start_time, "stopTime": experiment.stop_time},
        "studies": [
            {
                "index": i,
                "name": study.name,
                "entry": study.entry,
                "activities": [
                    _activity_info(j, a) for j, a in enumerate(study.activities)
                ],
                "domains": [_domain_info(d) for d in study.domains],
            }
            for i, study in enumerate(pkg.uq.studies())
        ],
    }


def _print_description(info: dict, out) -> None:
    print(f"{info['package']} (system {info['system']!r})", file=out)
    if not info["studies"]:
        print("  no omuq study attached", file=out)
    for study in info["studies"]:
        print(f"  study {study['index']}: {study['name']}", file=out)
        for act in study["activities"]:
            label = act["id"] or act["name"] or ""
            grid = ""
            if act["stopTime"] is not None or act["interval"] is not None:
                grid = f", stop={act['stopTime']}, interval={act['interval']}"
            print(
                f"    activity {act['index']}: {act['type']} {label}".rstrip()
                + f" (observes {len(act['observed'])}{grid})",
                file=out,
            )
        for dom in study["domains"]:
            print(
                f"    domain {dom['id']}: {dom['kind']}, "
                f"{dom['geometry'] or 'no boundary'} over {', '.join(dom['axes'])}",
                file=out,
            )


@contextlib.contextmanager
def _json_stdout():
    """Yield a stream on the real standard output; send fd 1 to standard error.

    Native code (OMSimulator) writes to file descriptor 1 directly, so
    rebinding ``sys.stdout`` alone would not keep it out of the JSON stream.
    """
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    out = os.fdopen(os.dup(saved), "w", encoding="utf-8", buffering=1)
    try:
        yield out
    finally:
        out.close()
        sys.stdout = real_stdout
        os.dup2(saved, 1)
        os.close(saved)


class _JsonEvents:
    """Write one JSON object per line and flush it."""

    def __init__(self, out):
        self._out = out

    def __call__(self, event: str, **payload) -> None:
        self._out.write(json.dumps({"event": event, **payload}, default=str) + "\n")
        self._out.flush()


class _EventSink:
    """Sink turning samples into ``sample`` and ``exit`` events."""

    def __init__(self, emit, every: int):
        self._emit = emit
        self._every = every
        self._seen = 0
        self._outside: set[str] = set()

    def on_start(self, names: Sequence[str]) -> None:
        self._seen = 0
        self._outside.clear()

    def on_sample(self, sample) -> None:
        outside = [v.domain_id for v in sample.violations]
        for v in sample.violations:
            if v.domain_id not in self._outside:
                self._emit(
                    "exit",
                    time=v.time,
                    domain=v.domain_id,
                    kind=v.domain_kind,
                    point=list(v.point),
                )
        self._outside = set(outside)
        if self._seen % self._every == 0:
            self._emit(
                "sample",
                time=sample.time,
                values=list(sample.values.values()),
                outside=outside,
            )
        self._seen += 1

    def on_finish(self) -> None:
        pass


def _cmd_list(args) -> int:
    info = describe_package(args.package)
    if args.json:
        json.dump(info, sys.stdout, indent=2)
        print()
    else:
        _print_description(info, sys.stdout)
    return 0


def _cmd_validate(args) -> int:
    from .package import SspPackage

    report = SspPackage.open(args.package).uq.validate(level=args.level)
    if args.json:
        doc = {
            "format": JSON_FORMAT_VERSION,
            "ok": report.ok,
            "issues": [
                {
                    "level": i.level,
                    "code": i.code,
                    "message": i.message,
                    "location": i.location,
                }
                for i in report.issues
            ],
        }
        json.dump(doc, sys.stdout, indent=2)
        print()
    else:
        print(report)
    return 0 if report.ok else 2


def _run(args, emit) -> None:
    from .drivers import auto_driver
    from .package import SspPackage
    from .simulation import CsvSink, MemorySink, PrintSink, Simulation

    package = Path(args.package).resolve()
    csv_out = Path(args.csv).resolve() if args.csv else None
    results_out = Path(args.output).resolve() if args.output else None
    prefer = ("local", "docker") if args.driver == "auto" else (args.driver,)

    pkg = SspPackage.open(package)
    if not pkg.uq.studies():
        raise OmuqError(f"no omuq study is attached to {package}")
    attached = pkg.uq.study(_key(args.study))
    activity = model.activity_of(attached.document, _key(args.activity))

    # The simulator writes its own result file into the working directory;
    # keep that out of the caller's directory.
    with tempfile.TemporaryDirectory(prefix="omuq-") as workdir:
        cwd = os.getcwd()
        os.chdir(workdir)
        try:
            driver = auto_driver(package, system=pkg.ssd().system_name, prefer=prefer)
            sim = Simulation.from_package(
                pkg,
                study=_key(args.study),
                activity=_key(args.activity),
                driver=driver,
                step=args.step,
                stop=args.stop,
            )
            mem = MemorySink()
            sim.subscribe(mem)
            if csv_out is not None:
                sim.subscribe(CsvSink(csv_out))
            if emit is not None:
                sim.subscribe(_EventSink(emit, args.every))
            else:
                sim.subscribe(PrintSink(every=args.every))
            ui = sim.watch(open_browser=emit is None) if args.ui else None
            if emit is not None:
                emit(
                    "start",
                    format=JSON_FORMAT_VERSION,
                    package=str(package),
                    study=attached.name,
                    activity=_activity_info(
                        model.activities_of(attached.document).index(activity),
                        activity,
                    ),
                    driver=type(driver).__name__,
                    names=list(sim._names),
                    start=sim._start,
                    stop=sim._stop,
                    step=sim._step,
                    domains=sim._domain_inventory(),
                    ui=ui.url if ui is not None else None,
                )
            result = sim.run()
        finally:
            os.chdir(cwd)

    summary = {
        "steps": result.steps,
        "end_time": result.end_time,
        "ok": result.ok,
        "monitored": list(result.monitored_domains),
        "samples_outside": result.samples_outside,
        "exits": result.exits,
        "skipped": [{"id": d, "reason": r} for d, r in result.skipped_domains],
        "text": result.summary(),
    }
    if emit is not None:
        emit("summary", **summary)
    else:
        print(result.summary())

    if results_out is not None:
        pkg.uq.record_result(attached, result, activity=activity, samples=mem.samples)
        pkg.save(results_out)
    if emit is not None:
        emit(
            "artifacts",
            csv=str(csv_out) if csv_out else None,
            results=str(results_out) if results_out else None,
        )
    else:
        for label, path in (("csv", csv_out), ("results", results_out)):
            if path is not None:
                print(f"{label}: {path}")

    if ui is not None:
        # Keep serving the finished run until the caller stops the process.
        ui.wait()


def _cmd_run(args) -> int:
    if not args.json:
        _run(args, None)
        return 0
    with _json_stdout() as out:
        emit = _JsonEvents(out)
        try:
            _run(args, emit)
        except (OmuqError, OSError) as exc:
            emit("error", message=str(exc))
            return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omuq",
        description="Inspect, validate and simulate omuq studies in SSP packages.",
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("package", help="the SSP package (.ssp)")
        p.add_argument(
            "--json", action="store_true", help="print machine-readable JSON"
        )

    p = sub.add_parser("list", help="list the attached studies, activities, domains")
    common(p)
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("validate", help="validate the omuq data in the package")
    common(p)
    p.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="1 schema, 2 links, 3 model names (default 3)",
    )
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser(
        "run", help="simulate one activity and monitor the study's domains"
    )
    common(p)
    p.add_argument("--study", help="study position or name (default 0)")
    p.add_argument("--activity", help="activity position, id or name (default 0)")
    p.add_argument(
        "--driver",
        choices=("auto", "local", "docker"),
        default="auto",
        help="simulator backend (default auto: local OMSimulator, then docker)",
    )
    p.add_argument("--step", type=float, help="override the communication step")
    p.add_argument("--stop", type=float, help="override the stop time")
    p.add_argument("--csv", help="write the observed samples to this CSV file")
    p.add_argument(
        "--output",
        help="record the run in the study and save the package to this .ssp",
    )
    p.add_argument(
        "--every",
        type=int,
        default=1,
        help="report every N-th sample (default 1); CSV and results keep all",
    )
    p.add_argument(
        "--ui",
        action="store_true",
        help="serve the live web view; keeps serving after the run until stopped",
    )
    p.set_defaults(func=_cmd_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "every", 1) < 1:
        parser.error("--every must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    try:
        return args.func(args)
    except OmuqError as exc:
        print(f"omuq: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
