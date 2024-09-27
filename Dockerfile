# https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye
ENV DEBIAN_FRONTEND=noninteractive
ARG APT_PROXY
ARG APT_CONF_PATH=/etc/apt/apt.conf.d/01proxy
RUN if [ -n "$APT_PROXY" ]; then \
      echo "Acquire::http::Proxy \"$APT_PROXY\";" > $APT_CONF_PATH; \
      cat $APT_CONF_PATH; \
    fi
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY . /workspace/youtube-whisperer
WORKDIR /workspace/youtube-whisperer
ARG PYPI_PROXY
ARG PIP_CONF_PATH=/root/.pip/pip.conf
# pin dependency versions by installing from the lock file before installing this project
RUN if [ -n "$PYPI_PROXY" ]; then \
      mkdir -p $(dirname $PIP_CONF_PATH); \
      PYPI_HOST=$(echo "$PYPI_PROXY" | sed -E 's|https?://([^:]+):.*|\1|'); \
      echo "[global]" > $PIP_CONF_PATH; \
      echo "index-url = $PYPI_PROXY" >> $PIP_CONF_PATH; \
      echo "trusted-host = $PYPI_HOST" >> $PIP_CONF_PATH; \
      cat $PIP_CONF_PATH; \
    fi
RUN pip --disable-pip-version-check --no-cache-dir install -r requirements.txt && \
    pip --disable-pip-version-check --no-cache-dir install --editable .
USER vscode
