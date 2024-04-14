# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
    && git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git \
    && ( cd nv-codec-headers && make install ) \
    && rm -rf nv-codec-headers

COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp
