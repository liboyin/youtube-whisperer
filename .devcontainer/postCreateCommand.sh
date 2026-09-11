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
# does not ship; the codex CLI itself comes from the ChatGPT extension. See TODO B1.
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex@openai-codex
