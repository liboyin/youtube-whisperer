# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG APT_PROXY=http://192.168.0.4:3142
ARG PYPI_PROXY=http://192.168.0.4:3141/root/pypi/+simple/
ENV DEBIAN_FRONTEND=noninteractive

COPY . /workspaces/youtube-whisperer
WORKDIR /workspaces/youtube-whisperer

RUN ./docker_apt_install.sh
RUN ./docker_pip_install.sh

USER vscode
