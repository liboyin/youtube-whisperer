FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04

ARG APT_PROXY
ARG PYPI_PROXY

ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_DRIVER_CAPABILITIES=all \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspaces/youtube-whisperer

# Install OS packages and pinned Python dependencies first, so editing source does not
# invalidate these layers and force a full dependency reinstall on every rebuild.
COPY --chown=ubuntu docker_apt_install.sh docker_pip_install.sh requirements.txt ./
RUN ./docker_apt_install.sh
RUN ./docker_pip_install.sh

# Copy the rest of the source and install the project itself in editable mode.
COPY --chown=ubuntu . .
RUN pip install -e .

USER ubuntu
