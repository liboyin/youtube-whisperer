# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends ffmpeg

COPY . /workspace/youtube_whisperer
WORKDIR /workspace/youtube_whisperer
# pin dependency versions by installing from the lock file before installing this project
RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt && \
    pip3 --disable-pip-version-check --no-cache-dir install --editable .
USER vscode
ENTRYPOINT ["/bin/bash"]
