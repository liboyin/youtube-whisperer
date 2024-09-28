#!/bin/bash

# Configure PyPI proxy. Note PIP_CONF_PATH depends on the current user
if [ -n "$PYPI_PROXY" ] && [ -n "$PIP_CONF_PATH" ]; then
    mkdir -p "$(dirname "$PIP_CONF_PATH")"
    cat <<EOF > "$PIP_CONF_PATH"
[global]
index-url = $PYPI_PROXY
trusted-host = $(echo "$PYPI_PROXY" | sed -E 's|https?://([^:/]+).*|\1|')
EOF
    cat "$PIP_CONF_PATH"
fi

# Pin dependency versions by installing from the lock file before installing this project
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
pip --disable-pip-version-check --no-cache-dir install --editable .
