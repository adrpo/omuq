"""Backend selection (``auto_driver``), ``FunctionDriver``, and from_package.

The auto_driver probes are exercised without OMSimulator and without docker:
the local probe is faked through ``sys.modules``, the docker probe through
``shutil.which`` and ``subprocess.run``.
"""

import io
import logging
import platform as platform_module
import subprocess
import sys
import types

import pytest
from conftest import SSD, FakeDriver, build_ssp, make_activity, study_with_domains

from omuq import (
    DockerOMSimulatorDriver,
    DriverNotFoundError,
    FunctionDriver,
    OMSimulatorDriver,
    Simulation,
    SimulationError,
    SsdRootAnchor,
    SspPackage,
    auto_driver,
    model,
    simulation,
)

# -- auto_driver probes ----------------------------------------------------


class _FakeInstance:
    """Whatever ``SSP(...).instantiate()`` returns; never driven here."""


class _FakeSsp:
    opened: list = []

    def __init__(self, path):
        _FakeSsp.opened.append(path)

    def instantiate(self):
        return _FakeInstance()


@pytest.fixture()
def no_omsimulator(monkeypatch):
    """Make ``from OMSimulator import SSP`` fail, installed or not."""
    monkeypatch.setitem(sys.modules, "OMSimulator", None)


@pytest.fixture()
def fake_omsimulator(monkeypatch):
    """Make ``from OMSimulator import SSP`` yield a fake SSP class."""
    module = types.ModuleType("OMSimulator")
    module.SSP = _FakeSsp
    _FakeSsp.opened = []
    monkeypatch.setitem(sys.modules, "OMSimulator", module)
    return _FakeSsp


@pytest.fixture()
def no_docker(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)


@pytest.fixture()
def fake_docker(monkeypatch):
    """A docker executable whose ``image inspect`` succeeds; records argv."""
    probes: list[list[str]] = []
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(argv, **kwargs):
        probes.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return probes


def test_auto_driver_prefers_local_omsimulator(fake_omsimulator, tmp_path, caplog):
    ssp = tmp_path / "model.ssp"
    with caplog.at_level(logging.INFO, logger="omuq.drivers"):
        driver = auto_driver(ssp, system="plant")
    assert isinstance(driver, OMSimulatorDriver)
    assert fake_omsimulator.opened == [str(ssp)]
    assert driver._system == "plant"
    assert "OMSimulator" in caplog.text


def test_auto_driver_falls_back_to_docker(
    no_omsimulator, fake_docker, tmp_path, caplog
):
    ssp = tmp_path / "model.ssp"
    with caplog.at_level(logging.INFO, logger="omuq.drivers"):
        driver = auto_driver(ssp, system="plant", image="img", platform=None)
    assert isinstance(driver, DockerOMSimulatorDriver)
    assert fake_docker == [["/usr/bin/docker", "image", "inspect", "img"]]
    assert driver._image == "img"
    assert driver._system == "plant"
    assert driver._platform is None
    assert "docker" in caplog.text


@pytest.mark.parametrize(
    "machine,expected",
    [("arm64", "linux/amd64"), ("aarch64", "linux/amd64"), ("x86_64", None)],
)
def test_auto_driver_platform_auto_follows_machine(
    no_omsimulator, fake_docker, monkeypatch, tmp_path, machine, expected
):
    monkeypatch.setattr(platform_module, "machine", lambda: machine)
    driver = auto_driver(tmp_path / "model.ssp")
    assert driver._platform == expected


def test_auto_driver_explicit_platform_passes_through(
    no_omsimulator, fake_docker, monkeypatch, tmp_path
):
    monkeypatch.setattr(platform_module, "machine", lambda: "x86_64")
    driver = auto_driver(tmp_path / "model.ssp", platform="linux/arm64")
    assert driver._platform == "linux/arm64"


def test_auto_driver_skips_docker_without_the_image(
    no_omsimulator, monkeypatch, tmp_path
):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 1)
    )
    with pytest.raises(DriverNotFoundError, match="omuq-omsimulator"):
        auto_driver(tmp_path / "model.ssp")


def test_auto_driver_returns_the_fallback(no_omsimulator, no_docker, tmp_path, caplog):
    fallback = FunctionDriver(lambda t: [t])
    with caplog.at_level(logging.INFO, logger="omuq.drivers"):
        assert auto_driver(tmp_path / "model.ssp", fallback=fallback) is fallback
    assert "fallback" in caplog.text


def test_auto_driver_without_any_backend_raises(no_omsimulator, no_docker, tmp_path):
    with pytest.raises(DriverNotFoundError) as err:
        auto_driver(tmp_path / "model.ssp")
    message = str(err.value)
    assert "pip install OMSimulator" in message
    assert "docker/" in message


def test_auto_driver_prefer_order_and_unknown_probe(
    fake_omsimulator, fake_docker, tmp_path
):
    driver = auto_driver(tmp_path / "model.ssp", prefer=("docker", "local"))
    assert isinstance(driver, DockerOMSimulatorDriver)
    with pytest.raises(SimulationError, match="unknown driver probe"):
        auto_driver(tmp_path / "model.ssp", prefer=("magic",))


# -- FunctionDriver --------------------------------------------------------


def run_with(driver, names=("a", "b"), stop=1.0, step=0.5):
    seen: list = []
    sim = Simulation(driver, names, stop=stop, step=step)
    sim.subscribe(seen.append)
    sim.run()
    return seen


def test_function_driver_sequence_form():
    samples = run_with(FunctionDriver(lambda t: [t, 2 * t]))
    assert [s.values for s in samples] == [
        {"a": 0.0, "b": 0.0},
        {"a": 0.5, "b": 1.0},
        {"a": 1.0, "b": 2.0},
    ]


def test_function_driver_mapping_form_is_looked_up_by_name():
    samples = run_with(FunctionDriver(lambda t: {"b": 2 * t, "a": t}))
    assert [s.values for s in samples] == [
        {"a": 0.0, "b": 0.0},
        {"a": 0.5, "b": 1.0},
        {"a": 1.0, "b": 2.0},
    ]


def test_function_driver_mapping_missing_name_raises():
    with pytest.raises(SimulationError, match="'b'"):
        run_with(FunctionDriver(lambda t: {"a": t}))


def test_function_driver_sequence_length_mismatch_raises():
    with pytest.raises(SimulationError, match="2 observed variable"):
        run_with(FunctionDriver(lambda t: [t]))


# -- Simulation.from_package -----------------------------------------------

#: The fixture SSD says startTime="0.0" stopTime="1.0"; these are variants.
SSD_LATE_START = SSD.replace('startTime="0.0"', 'startTime="0.5"')
SSD_NO_EXPERIMENT = SSD.replace(
    '  <ssd:DefaultExperiment startTime="0.0" stopTime="1.0"/>\n', ""
)


def package_with(activities, *, name="PkgStudy", ssd=SSD):
    pkg = SspPackage.open(io.BytesIO(build_ssp(ssd)))
    pkg.uq.attach(model.study(name, activities=list(activities)), SsdRootAnchor())
    return pkg


def test_explicit_arguments_win_over_the_documents():
    pkg = package_with([make_activity(observed=("a",), interval=0.25, stop_time=5.0)])
    drv = FakeDriver()
    Simulation.from_package(pkg, driver=drv, step=0.5, stop=2.0, start=1.0).run()
    assert drv.calls[0] == ("initialize", 1.0, 2.0, 0.5, ("a",))


def test_simulation_setting_wins_over_default_experiment():
    pkg = package_with([make_activity(observed=("a",), interval=0.5, stop_time=5.0)])
    drv = FakeDriver()
    Simulation.from_package(pkg, driver=drv).run()
    assert drv.calls[0] == ("initialize", 0.0, 5.0, 0.5, ("a",))


def test_default_experiment_supplies_stop_and_start():
    pkg = package_with(
        [make_activity(observed=("a",), interval=0.25)], ssd=SSD_LATE_START
    )
    drv = FakeDriver()
    Simulation.from_package(pkg, driver=drv).run()
    assert drv.calls[0] == ("initialize", 0.5, 1.0, 0.25, ("a",))


def test_missing_stop_everywhere_raises():
    pkg = package_with(
        [make_activity(observed=("a",), interval=0.25)], ssd=SSD_NO_EXPERIMENT
    )
    with pytest.raises(SimulationError, match="stopTime"):
        Simulation.from_package(pkg, driver=FakeDriver())


def test_missing_step_raises_even_with_a_default_experiment():
    pkg = package_with([make_activity(observed=("a",), stop_time=2.0)])
    with pytest.raises(SimulationError, match="interval"):
        Simulation.from_package(pkg, driver=FakeDriver())


def test_study_selected_by_index_and_name():
    pkg = package_with(
        [make_activity(observed=("a",), interval=0.5, stop_time=1.0)], name="First"
    )
    pkg.uq.attach(
        model.study(
            "Second",
            activities=[make_activity(observed=("b",), interval=0.5, stop_time=1.0)],
        ),
        SsdRootAnchor(),
    )
    for key, expected in [(0, ("a",)), (1, ("b",)), ("Second", ("b",))]:
        drv = FakeDriver()
        Simulation.from_package(pkg, study=key, driver=drv).run()
        assert drv.calls[0][4] == expected


def test_activity_selected_by_index_id_and_name():
    pkg = package_with(
        [
            make_activity(observed=("a",), interval=0.5, stop_time=1.0),
            model.validation(
                observed=["b"], step=0.25, stop=1.0, id="second", name="Val"
            ),
        ]
    )
    for key in (1, "second", "Val"):
        drv = FakeDriver()
        Simulation.from_package(pkg, activity=key, driver=drv).run()
        assert drv.calls[0] == ("initialize", 0.0, 1.0, 0.25, ("b",))


def test_package_without_studies_raises():
    pkg = SspPackage.open(io.BytesIO(build_ssp()))
    with pytest.raises(SimulationError, match="no omuq study"):
        Simulation.from_package(pkg, driver=FakeDriver())


def test_file_object_package_without_a_driver_raises():
    pkg = package_with([make_activity(observed=("a",), interval=0.5, stop_time=1.0)])
    assert pkg.path is None
    with pytest.raises(SimulationError, match="driver="):
        Simulation.from_package(pkg)


def test_auto_driver_gets_the_path_system_and_fallback(tmp_path, monkeypatch):
    pkg = package_with([make_activity(observed=("a",), interval=0.5, stop_time=1.0)])
    path = tmp_path / "study.ssp"
    pkg.save(path)
    fallback = FunctionDriver(lambda t: [t])
    seen = {}

    def fake_auto_driver(ssp_path, **kwargs):
        seen["path"] = ssp_path
        seen.update(kwargs)
        return FakeDriver()

    monkeypatch.setattr(simulation, "auto_driver", fake_auto_driver)
    sim = Simulation.from_package(path, fallback_driver=fallback)
    assert seen["path"] == path
    assert seen["system"] == "plant"  # the SSD root system name
    assert seen["fallback"] is fallback
    assert sim.run().steps == 2


def test_from_package_monitors_the_studys_domains():
    pkg = SspPackage.open(io.BytesIO(build_ssp()))
    pkg.uq.attach(study_with_domains(name="Monitored"), SsdRootAnchor())
    result = Simulation.from_package(pkg, driver=FakeDriver()).run()
    assert result.monitored_domains == ("od", "dov")
    assert "someParameter" in dict(result.skipped_domains)["paramDomain"]
