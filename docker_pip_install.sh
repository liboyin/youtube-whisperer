#!/bin/bash

set -euo pipefail

PIP_CONF_PATH=$HOME/.pip/pip.conf
mkdir -p "$(dirname "$PIP_CONF_PATH")"
cat <<EOF > "$PIP_CONF_PATH"
[global]
break-system-packages = true
disable-pip-version-check = true
no-cache-dir = true
no-compile = true
root-user-action = ignore
EOF

# Configure PyPI proxy (skipped when PYPI_PROXY is unset or empty)
if [ -n "${PYPI_PROXY:-}" ]; then
    cat <<EOF >> "$PIP_CONF_PATH"
index-url = $PYPI_PROXY
trusted-host = $(echo "$PYPI_PROXY" | sed -E 's|https?://([^:/]+).*|\1|')
EOF
fi

cat "$PIP_CONF_PATH"

# Pin dependency versions from the lock file. The project itself is installed separately
# (via `pip install -e .` after the source is copied) so editing source does not reinstall deps.
if [ -s "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Remove pip cache
pip_cache_dirs=(
    "/tmp/pip-tmp"
    "$HOME/.cache/pip"
)
for dir_path in "${pip_cache_dirs[@]}"; do
    if [ -d "$dir_path" ]; then
        echo "Removing pip cache dir: $dir_path"
        rm -rf "$dir_path"
    fi
done
