# OMSimulator execution image

OMSimulator has no macOS build, so `omuq.DockerOMSimulatorDriver` runs the
simulation inside this container while the omuq SDK (monitoring, subscribers,
CSV sinks) runs on the host.

Build the image (x86-64 only; on Apple Silicon it runs under emulation):

```bash
docker build --platform linux/amd64 -t omuq-omsimulator docker/
```

Use it from the SDK:

```python
from omuq import DockerOMSimulatorDriver, Simulation

driver = DockerOMSimulatorDriver(
    "examples/ScrewTrajectory.ssp",
    platform="linux/amd64",  # on Apple Silicon
)
sim = Simulation.for_study(study, driver)
sim.run()
```

The directory containing the `.ssp` file is mounted read-only at `/data`
inside the container. `docker/run_simulation.py` loads the SSP with
OMSimulator and streams one CSV line per communication step to stdout, which
the driver consumes live.
