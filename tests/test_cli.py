"""The ``omuq`` command line interface (``omuq.cli``).

Runs go through ``FakeDriver`` (value of the i-th name at time t is
t + 10*i) by patching ``auto_driver``, so no simulator is needed. With the
fixture study, ``a`` equals t, so the domain of validation ``dov``
(0 <= a <= 0.25) is left once, at t=0.5, and stays left until t=1.
"""

import json
import os
import subprocess
import sys

import pytest
from conftest import FakeDriver, build_ssp, study_with_domains

from omuq import SsdRootAnchor, SspPackage, cli, model


@pytest.fixture()
def study_ssp(tmp_path):
    pkg = SspPackage.open(_write(tmp_path / "plain.ssp", build_ssp()))
    pkg.uq.attach(study_with_domains(name="Monitored"), SsdRootAnchor())
    path = tmp_path / "study.ssp"
    pkg.save(path)
    return path


@pytest.fixture()
def fake_backend(monkeypatch):
    """Make the CLI's driver selection return a FakeDriver; records calls."""
    calls = []

    def fake_auto_driver(path, **kwargs):
        calls.append((path, kwargs))
        return FakeDriver()

    monkeypatch.setattr("omuq.drivers.auto_driver", fake_auto_driver)
    return calls


def _write(path, data):
    path.write_bytes(data)
    return path


def _events(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_list_json_describes_studies_activities_and_domains(study_ssp, capsys):
    assert cli.main(["list", str(study_ssp), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["format"] == cli.JSON_FORMAT_VERSION
    assert doc["system"] == "plant"
    assert doc["defaultExperiment"] == {"startTime": 0.0, "stopTime": 1.0}
    (study,) = doc["studies"]
    assert study["name"] == "Monitored"
    (act,) = study["activities"]
    assert act["type"] == "ForwardUncertaintyQuantification"
    assert act["observed"] == ["a", "b"]
    assert (act["stopTime"], act["interval"]) == (1.0, 0.25)
    assert [d["id"] for d in study["domains"]] == ["od", "dov", "paramDomain"]
    assert study["domains"][1]["geometry"] == "HyperRectangle"


def test_list_text_and_a_package_without_studies(tmp_path, study_ssp, capsys):
    assert cli.main(["list", str(study_ssp)]) == 0
    out = capsys.readouterr().out
    assert "study 0: Monitored" in out
    assert "activity 0: ForwardUncertaintyQuantification" in out

    plain = _write(tmp_path / "plain2.ssp", build_ssp())
    assert cli.main(["list", str(plain), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["studies"] == []
    assert cli.main(["list", str(plain)]) == 0
    assert "no omuq study attached" in capsys.readouterr().out


def test_validate_json(study_ssp, capsys):
    status = cli.main(["validate", str(study_ssp), "--json", "--level", "2"])
    doc = json.loads(capsys.readouterr().out)
    assert status == (0 if doc["ok"] else 2)
    assert all(
        {"level", "code", "message", "location"} <= set(i) for i in doc["issues"]
    )


def test_run_json_streams_events_and_writes_artifacts(
    study_ssp, tmp_path, fake_backend, capfd
):
    csv_out = tmp_path / "run.csv"
    results_out = tmp_path / "results.ssp"
    status = cli.main(
        [
            "run",
            str(study_ssp),
            "--json",
            "--csv",
            str(csv_out),
            "--output",
            str(results_out),
        ]
    )
    out = capfd.readouterr().out
    assert status == 0
    events = _events(out)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "start" and kinds[-2:] == ["summary", "artifacts"]

    start = events[0]
    assert start["study"] == "Monitored"
    assert start["names"] == ["a", "b"]
    assert (start["start"], start["stop"], start["step"]) == (0.0, 1.0, 0.25)
    assert start["driver"] == "FakeDriver"
    assert {d["id"]: d["monitored"] for d in start["domains"]} == {
        "od": True,
        "dov": True,
        "paramDomain": False,
    }

    samples = [e for e in events if e["event"] == "sample"]
    assert [s["time"] for s in samples] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert samples[2]["values"] == [0.5, 10.5]
    assert [s["outside"] for s in samples] == [[], [], ["dov"], ["dov"], ["dov"]]
    # One excursion, so one exit event, not one per sample outside.
    (exit_event,) = [e for e in events if e["event"] == "exit"]
    assert (exit_event["time"], exit_event["domain"]) == (0.5, "dov")

    summary = events[-2]
    assert summary["ok"] is False
    assert summary["exits"] == {"od": 0, "dov": 1}
    assert summary["samples_outside"] == {"od": 0, "dov": 3}
    assert summary["skipped"][0]["id"] == "paramDomain"

    assert events[-1] == {
        "event": "artifacts",
        "csv": str(csv_out),
        "results": str(results_out),
    }
    assert csv_out.read_text().splitlines()[0] == "time,a,b"
    recorded = SspPackage.open(results_out).uq.study(0).activities[0]
    assert model.results_of(recorded)

    ((path, kwargs),) = fake_backend
    assert path == study_ssp.resolve()
    assert kwargs["prefer"] == ("local", "docker")


def test_run_json_keeps_native_stdout_out_of_the_event_stream(
    study_ssp, monkeypatch, capfd
):
    """Writes to file descriptor 1 during the run land on standard error."""

    class NoisyDriver(FakeDriver):
        def advance(self, t):
            os.write(1, b"native chatter\n")
            print("python chatter")
            super().advance(t)

    monkeypatch.setattr("omuq.drivers.auto_driver", lambda *a, **k: NoisyDriver())
    assert cli.main(["run", str(study_ssp), "--json"]) == 0
    captured = capfd.readouterr()
    assert "chatter" not in captured.out
    assert "native chatter" in captured.err
    assert "python chatter" in captured.err
    _events(captured.out)  # every stdout line is JSON


def test_run_every_throttles_samples_only(study_ssp, fake_backend, capfd):
    assert cli.main(["run", str(study_ssp), "--json", "--every", "2"]) == 0
    events = _events(capfd.readouterr().out)
    assert [e["time"] for e in events if e["event"] == "sample"] == [0.0, 0.5, 1.0]
    assert len([e for e in events if e["event"] == "exit"]) == 1


def test_run_selects_driver_and_leaves_no_files_in_cwd(
    study_ssp, tmp_path, fake_backend, capfd, monkeypatch
):
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    assert cli.main(["run", str(study_ssp), "--json", "--driver", "docker"]) == 0
    assert fake_backend[0][1]["prefer"] == ("docker",)
    assert os.getcwd() == str(workdir)
    assert list(workdir.iterdir()) == []


def test_run_text_mode(study_ssp, fake_backend, capfd):
    assert cli.main(["run", str(study_ssp), "--every", "4"]) == 0
    out = capfd.readouterr().out
    assert "4 steps to t=1" in out
    assert "dov: 3 samples outside in 1 excursion" in out


def test_run_errors_are_json_events(tmp_path, study_ssp, fake_backend, capfd):
    plain = _write(tmp_path / "plain3.ssp", build_ssp())
    assert cli.main(["run", str(plain), "--json"]) == 1
    (event,) = _events(capfd.readouterr().out)
    assert event["event"] == "error"
    assert "no omuq study" in event["message"]

    assert cli.main(["run", str(study_ssp), "--json", "--activity", "nope"]) == 1
    (event,) = _events(capfd.readouterr().out)
    assert event["event"] == "error"
    assert "nope" in event["message"]


def test_run_rejects_every_below_one(study_ssp):
    with pytest.raises(SystemExit):
        cli.main(["run", str(study_ssp), "--every", "0"])


def test_python_dash_m_omuq(study_ssp):
    result = subprocess.run(
        [sys.executable, "-m", "omuq", "list", str(study_ssp), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["studies"][0]["name"] == "Monitored"
