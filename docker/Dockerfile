# OMSimulator execution image for omuq.DockerOMSimulatorDriver.
#
# OMSimulator has no macOS build and ships x86-64 wheels only, so build (and
# run) this image for linux/amd64; on Apple Silicon it runs under emulation:
#
#     docker build --platform linux/amd64 -t omuq-omsimulator docker/
#
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir OMSimulator

COPY run_simulation.py /opt/omuq/run_simulation.py

# -u: unbuffered stdout, so the host receives each sample line as it happens.
ENTRYPOINT ["python", "-u", "/opt/omuq/run_simulation.py"]
