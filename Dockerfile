FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG APT_PROXY
ARG PYPI_PROXY

ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_DRIVER_CAPABILITIES=all
ENV PYTHONFAULTHANDLER=1

RUN useradd -m ubuntu
COPY --chown=ubuntu . /workspaces/youtube-whisperer
WORKDIR /workspaces/youtube-whisperer

RUN ./docker_apt_install.sh
RUN ./docker_pip_install.sh

USER ubuntu
