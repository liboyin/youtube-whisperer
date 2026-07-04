#!/bin/bash

set -euo pipefail

# Configure APT proxy (skipped when APT_PROXY is unset or empty)
if [ -n "${APT_PROXY:-}" ]; then
    APT_CONF_PATH=/etc/apt/apt.conf.d/01proxy
    echo "Acquire::http::Proxy \"$APT_PROXY\";" > $APT_CONF_PATH
    cat $APT_CONF_PATH
fi

apt-get update
apt-get install -y --no-install-recommends curl ffmpeg git python3 python3-pip unzip
export DENO_INSTALL=/usr/local && curl -fsSL https://deno.land/install.sh | sh
ln -s "$(which python3)" "$(dirname "$(which python3)")/python"
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/*
