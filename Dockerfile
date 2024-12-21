FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG APT_PROXY=http://192.168.0.4:3142
ARG PYPI_PROXY=http://192.168.0.4:3141/root/pypi/+simple/
ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_DRIVER_CAPABILITIES=all

COPY . /workspaces/youtube-whisperer
WORKDIR /workspaces/youtube-whisperer

RUN useradd -m ubuntu && \
    chown -R ubuntu:ubuntu /workspaces/youtube-whisperer

RUN ./docker_apt_install.sh
RUN ./docker_pip_install.sh

USER ubuntu
