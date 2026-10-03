#! /bin/bash
set -euo pipefail
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as root, but current user is ubuntu
sudo pip install -e .[dev]
# use native installer of Claude Code
curl -fsSL https://claude.ai/install.sh | bash
# Install standalone Codex for direct CLI review, without prompting or launching a session.
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh
# Both installers use this directory; this non-interactive shell has not picked it up.
export PATH="$HOME/.local/bin:$PATH"
codex --version
