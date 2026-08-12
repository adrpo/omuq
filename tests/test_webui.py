import http.client
import json
import socket
import threading
import time
import urllib.request

import pytest
from conftest import FakeDriver, make_activity, rect_domain, study_with_domains

from omuq import Simulation, SimulationError
from omuq.webui import WebUi, _EventBus

# -- helpers ---------------------------------------------------------------


def get(url, timeout=5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


def read_sse(port, until, deadline=10.0):
    """Collect (event, payload) pairs from /api/events until `until(events)`."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
    events = []
    try:
        conn.request("GET", "/api/events")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.headers["Content-Type"].startswith("text/event-stream")
        end = time.monotonic() + deadline
        event = None
        while time.monotonic() < end and not until(events):
            try:
                raw = resp.fp.readline()
            except TimeoutError:
                continue
            if not raw:
                break
            line = raw.decode().rstrip("\n")
            if line.startswith(":"):
                events.append((":comment", None))
            elif line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: ") and event is not None:
                events.append((event, json.loads(line[len("data: ") :])))
                event = None
    finally:
        conn.close()
    return events


def data_events(events):
    return [e for e in events if e[0] != ":comment"]


def finished(events):
    return any(e == ("status", {"state": "finished"}) for e in data_events(events))


# -- server basics ---------------------------------------------------------


INVENTORY = [
    {
        "id": "hullDom",
        "name": "Hull",
        "kind": "Validation",
        "monitored": True,
        "reason": None,
        "geometry": "hull",
        "axes": ["a", "b"],
        "vertices": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
    },
    {
        "id": "other",
        "name": None,
        "kind": "Calibration",
        "monitored": False,
        "reason": "axes are not observed variables of this run: p",
        "geometry": "rect",
        "axes": ["p"],
        "vertices": [[0.0], [1.0]],
    },
]


@pytest.fixture()
def ui():
    handle = WebUi(
        names=["a", "b"],
        start=0.0,
        stop=1.0,
        step=0.5,
        domains=INVENTORY,
        study="S",
        open_browser=False,
    )
    yield handle
    handle.close()


def test_init_payload_lists_all_domains(ui):
    status, _, body = get(ui.url + "api/init")
    assert status == 200
    init = json.loads(body)
    assert init["names"] == ["a", "b"]
    assert init["study"] == "S"
    assert (init["start"], init["stop"], init["step"]) == (0.0, 1.0, 0.5)
    by_id = {d["id"]: d for d in init["domains"]}
    assert by_id["hullDom"]["monitored"] is True
    assert by_id["hullDom"]["vertices"] == [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    assert by_id["other"]["monitored"] is False
    assert "not observed variables" in by_id["other"]["reason"]


def test_index_and_plotly_served(ui):
    status, headers, body = get(ui.url)
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"/static/plotly.min.js" in body
    status, headers, body = get(ui.url + "static/plotly.min.js")
    assert status == 200
    assert "javascript" in headers["Content-Type"]
    assert "max-age" in headers["Cache-Control"]
    assert len(body) > 100_000


def test_unknown_path_404(ui):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(ui.url + "nope")
    assert err.value.code == 404


def test_heartbeat_comment_when_idle():
    handle = WebUi(
        names=["a"],
        start=0.0,
        stop=1.0,
        step=0.5,
        domains=[],
        open_browser=False,
        heartbeat=0.2,
    )
    try:
        port = handle._server.server_address[1]
        events = read_sse(
            port,
            until=lambda ev: any(e[0] == ":comment" for e in ev),
            deadline=5.0,
        )
        assert any(e[0] == ":comment" for e in events)
    finally:
        handle.close()


# -- streaming a real run --------------------------------------------------


def run_watched_sim():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.monitor(rect_domain())  # a in [0, 0.25] -> violated at t=0.5, 1.0
    ui = sim.watch(open_browser=False)
    return sim, ui


def test_stream_replays_full_run():
    sim, ui = run_watched_sim()
    try:
        result = sim.run()
        port = ui._server.server_address[1]
        events = data_events(read_sse(port, until=finished))
        assert events[0] == ("status", {"state": "waiting"})
        assert events[1] == ("status", {"state": "running"})
        samples = [e[1] for e in events if e[0] == "sample"]
        assert [s["t"] for s in samples] == [0.0, 0.5, 1.0]
        assert samples[1]["values"] == {"a": 0.5}
        assert samples[0]["violations"] == []
        assert samples[1]["violations"] == [{"id": "dov", "kind": "Validation"}]
        summary = next(e[1] for e in events if e[0] == "summary")
        assert summary["steps"] == 2
        assert summary["samples"] == 3
        assert summary["end_time"] == 1.0
        assert summary["counts"] == result.samples_outside == {"dov": 2}
        assert events[-1] == ("status", {"state": "finished"})
    finally:
        ui.close()


def test_late_connect_replay_equals_live():
    sim, ui = run_watched_sim()
    try:
        port = ui._server.server_address[1]
        live: list = []

        def reader():
            live.extend(data_events(read_sse(port, until=finished)))

        thread = threading.Thread(target=reader)
        thread.start()
        time.sleep(0.2)  # let the live client attach first
        sim.run()
        thread.join(timeout=10)
        assert not thread.is_alive()
        late = data_events(read_sse(port, until=finished))
        assert live == late
        assert finished(late)
    finally:
        ui.close()


def test_watch_inventory_from_study():
    sim = Simulation.for_study(study_with_domains(name="WebUiStudy"), FakeDriver())
    ui = sim.watch(open_browser=False)
    try:
        _, _, body = get(ui.url + "api/init")
        init = json.loads(body)
        assert init["study"] == "WebUiStudy"
        by_id = {d["id"]: d for d in init["domains"]}
        assert set(by_id) == {"od", "dov", "paramDomain"}
        assert by_id["od"]["monitored"] and by_id["od"]["geometry"] == "rect"
        assert by_id["od"]["vertices"] == [[-100.0, -100.0], [100.0, 100.0]]
        assert by_id["dov"]["kind"] == "Validation"
        assert by_id["paramDomain"]["monitored"] is False
        assert "someParameter" in by_id["paramDomain"]["reason"]
    finally:
        ui.close()


def test_watch_after_run_raises():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    sim.run()
    with pytest.raises(SimulationError, match="before run"):
        sim.watch(open_browser=False)


def test_close_idempotent_and_port_released(ui):
    port = ui._server.server_address[1]
    ui.close()
    ui.close()
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=1)


def test_context_manager_closes():
    act = make_activity(observed=("a",), interval=0.5, stop_time=1.0)
    sim = Simulation.for_activity(act, FakeDriver())
    with sim.watch(open_browser=False) as handle:
        port = handle._server.server_address[1]
        status, _, _ = get(handle.url + "api/init")
        assert status == 200
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=1)


# -- event bus white-box ---------------------------------------------------


def test_event_bus_replay_no_loss_no_dup():
    bus = _EventBus()
    bus.publish("a", {"n": 1})
    bus.publish("a", {"n": 2})
    bus.publish("a", {"n": 3})
    q = bus.subscribe()
    got = [q.get(timeout=1) for _ in range(3)]
    assert [g.decode().splitlines()[1] for g in got] == [
        'data: {"n":1}',
        'data: {"n":2}',
        'data: {"n":3}',
    ]
    bus.publish("a", {"n": 4})
    assert q.get(timeout=1).decode().splitlines()[1] == 'data: {"n":4}'
    bus.close()
    assert q.get(timeout=1) is None
    assert q.empty()
