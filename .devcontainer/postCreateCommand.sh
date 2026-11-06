#! /bin/bash
set -euo pipefail
# Add the locked dev group to the image's venv. --locked fails if uv.lock no longer matches
# pyproject.toml, and nothing here rewrites the lock: refreshing it is a deliberate `uv lock`.
# This talks to PyPI directly: a lock resolved against PyPI is reported stale behind the
# PYPI_PROXY mirror (see DESIGN.md, "Dependencies are locked and installed with uv").
uv sync --locked
# use native installer of Claude Code
curl -fsSL https://claude.ai/install.sh | bash
# Install standalone Codex for direct CLI review, without prompting or launching a session.
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh
# Both installers use this directory; this non-interactive shell has not picked it up.
export PATH="$HOME/.local/bin:$PATH"
codex --version
