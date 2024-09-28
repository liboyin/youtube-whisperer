# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

ARG APT_PROXY
ARG PYPI_PROXY
ARG PIP_CONF_PATH=/root/.pip/pip.conf
ENV DEBIAN_FRONTEND=noninteractive

COPY . /workspace/youtube-whisperer
WORKDIR /workspace/youtube-whisperer

RUN ./docker_apt_install.sh
RUN ./docker_pip_install.sh

USER vscode
