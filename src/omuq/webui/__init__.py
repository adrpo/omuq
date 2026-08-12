"""Live web view of a simulation run (see :meth:`omuq.Simulation.watch`).

A :class:`WebUi` is both a small local HTTP server and a simulation sink:
``sim.watch()`` constructs one, subscribes it, and opens the browser. The
page (``index.html``) fetches ``/api/init`` - the run description including
the full domain inventory - and then consumes ``/api/events``, a
Server-Sent-Events stream of ``status`` / ``sample`` / ``summary`` events.
Every published event is buffered, and each new stream client first
receives the complete history, so pages opened or refreshed late replay the
whole run. The server binds to 127.0.0.1 only and uses only the standard
library.

``on_finish`` is called from ``run()``'s ``finally`` block and cannot
distinguish success from failure; the page shows "finished" plus whatever
was streamed.

A vendored Plotly partial bundle is included (``static/plotly-gl3d.min.js``,
version :data:`PLOTLY_VERSION`), Copyright 2012-2026 Plotly, Inc., MIT
licensed; the license banner is embedded in the file itself.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import webbrowser
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources as _ilr

#: Version of the vendored plotly-gl3d bundle in ``static/``.
PLOTLY_VERSION = "3.7.0"


def _frame(event: str, payload: dict) -> bytes:
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n".encode()


class _EventBus:
    """Full event history plus live per-client queues, under one lock.

    ``publish`` and ``subscribe`` are serialized by the lock. For any frame
    and client, either the frame is already in the history when the client
    subscribes and is replayed, or the client's queue is already registered
    when the frame is published and receives it live. Each client sees every
    frame exactly once, in publish order.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._history: list[bytes] = []
        self._queues: list[queue.SimpleQueue] = []
        self._closed = False

    def publish(self, event: str, payload: dict) -> None:
        frame = _frame(event, payload)
        with self._lock:
            if self._closed:
                return
            self._history.append(frame)
            for q in self._queues:
                q.put(frame)

    def subscribe(self) -> queue.SimpleQueue:
        q: queue.SimpleQueue = queue.SimpleQueue()
        with self._lock:
            for frame in self._history:
                q.put(frame)
            if self._closed:
                q.put(None)
            else:
                self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.SimpleQueue) -> None:
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for q in self._queues:
                q.put(None)
            self._queues.clear()


_ASSETS: dict[str, bytes] = {}


def _asset(rel: str) -> bytes:
    if rel not in _ASSETS:
        node = _ilr.files("omuq.webui")
        for part in rel.split("/"):
            node = node / part
        _ASSETS[rel] = node.read_bytes()
    return _ASSETS[rel]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "omuq-webui"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def do_GET(self):
        self._route(head=False)

    def do_HEAD(self):
        self._route(head=True)

    def _route(self, head: bool):
        path = self.path.split("?", 1)[0]
        ui = self.server.ui
        try:
            if path == "/":
                self._send(
                    200, "text/html; charset=utf-8", _asset("index.html"), head=head
                )
            elif path == "/static/plotly.min.js":
                self._send(
                    200,
                    "text/javascript; charset=utf-8",
                    _asset("static/plotly-gl3d.min.js"),
                    cache="public, max-age=31536000, immutable",
                    head=head,
                )
            elif path == "/api/init":
                body = json.dumps(ui._init).encode()
                self._send(200, "application/json", body, cache="no-store", head=head)
            elif path == "/api/events":
                if head:
                    self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
                else:
                    self._stream(ui)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except OSError:
            pass  # client went away mid-response

    def _send(
        self,
        status: int,
        ctype: str,
        body: bytes,
        cache: str | None = None,
        head: bool = False,
    ):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _stream(self, ui: WebUi):
        q = ui._bus.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            while True:
                try:
                    frame = q.get(timeout=ui._heartbeat)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                if frame is None:
                    break
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            ui._bus.unsubscribe(q)


class WebUi:
    """Live web view of one simulation run; also a Simulation sink."""

    def __init__(
        self,
        *,
        names: Sequence[str],
        start: float,
        stop: float,
        step: float,
        domains: list[dict],
        study: str | None = None,
        title: str = "omuq live simulation",
        host: str = "127.0.0.1",
        port: int = 0,
        open_browser: bool = True,
        heartbeat: float = 15.0,
    ):
        self._init = {
            "title": title,
            "study": study,
            "names": list(names),
            "start": start,
            "stop": stop,
            "step": step,
            "domains": domains,
        }
        self._bus = _EventBus()
        self._heartbeat = heartbeat
        # Same semantics as SimulationResult.samples_outside; published under
        # the summary event's "counts" key, which the page's JS reads.
        self._samples_outside: dict[str, int] = {}
        self._samples = 0
        self._last_t: float | None = None
        self._stop_event = threading.Event()
        self._close_lock = threading.Lock()
        self._closed = False
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.ui = self
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="omuq-webui", daemon=True
        )
        self._thread.start()
        self._bus.publish("status", {"state": "waiting"})
        if open_browser:
            try:
                webbrowser.open(self.url)
            except Exception:
                pass  # headless: wait() prints the URL

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/"

    # -- Sink protocol (called on the simulation thread) -------------------

    def on_start(self, names: Sequence[str]) -> None:
        self._samples_outside = {
            d["id"]: 0 for d in self._init["domains"] if d.get("monitored")
        }
        self._samples = 0
        self._last_t = None
        self._bus.publish("status", {"state": "running"})

    def on_sample(self, sample) -> None:
        self._samples += 1
        self._last_t = sample.time
        for violation in sample.violations:
            self._samples_outside[violation.domain_id] = (
                self._samples_outside.get(violation.domain_id, 0) + 1
            )
        self._bus.publish(
            "sample",
            {
                "t": sample.time,
                "values": {
                    n: (v if math.isfinite(v) else None)
                    for n, v in sample.values.items()
                },
                "violations": [
                    {"id": v.domain_id, "kind": v.domain_kind}
                    for v in sample.violations
                ],
            },
        )

    def on_finish(self) -> None:
        self._bus.publish(
            "summary",
            {
                "steps": max(self._samples - 1, 0),
                "samples": self._samples,
                "end_time": self._last_t,
                "counts": dict(self._samples_outside),
            },
        )
        self._bus.publish("status", {"state": "finished"})

    # -- lifecycle ---------------------------------------------------------

    def wait(self) -> None:
        """Block until Ctrl+C (or :meth:`close` elsewhere), then shut down."""
        print(f"omuq webui: serving at {self.url} - press Ctrl+C to stop")
        try:
            while not self._stop_event.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._stop_event.set()
        self._bus.close()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def __enter__(self) -> WebUi:
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
