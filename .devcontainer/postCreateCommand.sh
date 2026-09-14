#! /bin/bash
set -euo pipefail
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as root, but current user is ubuntu
sudo pip install -e .[dev]
# use native installer of Claude Code
curl -fsSL https://claude.ai/install.sh | bash
# the installer drops the binary here, which this non-interactive shell has not picked up
export PATH="$HOME/.local/bin:$PATH"
# AGENTS.md requires adversarial review through the Codex plugin, which is now container-local.
# Both commands are idempotent. The plugin's companion scripts run under node, which this image
# does not ship; the codex CLI itself comes from the ChatGPT extension.
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex@openai-codex
# The review skill's codex CLI and the node runtime its companion scripts need are not on PATH,
# and the ChatGPT extension providing codex updates far more often than this container is rebuilt,
# so the version-stamped paths go stale. The resolver links them now and installs a shell hook
# that re-resolves them whenever a link is missing or broken.
python3 "$(dirname "$0")/link_review_tools.py" --install-hook
