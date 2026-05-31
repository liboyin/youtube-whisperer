#! /bin/bash
set -euo pipefail
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as root, but current user is ubuntu
sudo pip install -e .[dev]
# reclaim dirs Docker auto-created as root to mount ~/.claude/plugins/installed_plugins.json
sudo chown ubuntu:ubuntu /home/ubuntu/.claude /home/ubuntu/.claude/plugins
# use native installer of Claude Code
curl -fsSL https://claude.ai/install.sh | bash
