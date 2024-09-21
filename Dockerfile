# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY . /workspace/youtube-whisperer
WORKDIR /workspace/youtube-whisperer
# pin dependency versions by installing from the lock file before installing this project
RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt && \
    pip3 --disable-pip-version-check --no-cache-dir install --editable .
USER vscode
