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
# Neither tool is on PATH: node is bundled with the VS Code server and codex ships inside the
# ChatGPT extension, both behind version-stamped directories. VS Code installs that extension
# after this script finishes, so linking only here would leave codex missing on a fresh
# container. The helper is therefore idempotent and also runs on shell startup to self-heal.
helper="$HOME/.local/bin/link-review-tools"
helper_marker='# managed by .devcontainer/postCreateCommand.sh'
# Writing straight to the destination would truncate a user's own file of that name, or follow a
# symlink and truncate whatever it points at. Replace only an absent entry or a regular file
# carrying the marker, and stage through a temporary file so the destination is never opened for
# truncation. The regular-file test comes first so a FIFO or other special file is skipped rather
# than read, which would block this script indefinitely and stall container creation.
if [ -L "$helper" ] || { [ -e "$helper" ] && { [ ! -f "$helper" ] || ! grep -qxF "$helper_marker" "$helper" 2>/dev/null; }; }; then
    echo "postCreate: $helper is not managed here; leaving it alone and skipping tool links" >&2
else
helper_tmp="$(mktemp)"
cat > "$helper_tmp" <<'EOF'
#! /bin/bash
# managed by .devcontainer/postCreateCommand.sh
# Link the newest node and codex into ~/.local/bin for the adversarial review skill.
# Re-runnable by design: a tool that is not installed yet is skipped rather than failing, so a
# later shell picks it up once the ChatGPT extension lands.
set -uo pipefail
link_newest() {
    local name="$1" dest newest current candidate
    dest="$HOME/.local/bin/$name"
    # Walk candidates newest first and take the first executable one, so a partial or corrupt
    # newest install falls back to a usable older build instead of leaving the tool unlinked.
    newest=""
    while IFS= read -r candidate; do
        if [ -f "$candidate" ] && [ -x "$candidate" ]; then
            newest="$candidate"
            break
        fi
    done < <(ls -1dt "${@:2}" 2>/dev/null)
    if [ -z "$newest" ]; then
        return 0
    fi
    # Never destroy a user-managed tool. Replace only an absent entry or a link this helper
    # owns, identified by pointing into the VS Code server or extension trees; a regular file,
    # a directory, or a link to anything else is left alone.
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        current="$(readlink "$dest")" || return 0
        case "$current" in
            /vscode/vscode-server/*|"$HOME"/.vscode-server/extensions/*) ;;
            *) return 0 ;;
        esac
    fi
    ln -sfn "$newest" "$dest"
}
# Newest by mtime is a heuristic: several server builds can share a timestamp, and the tie is
# then broken arbitrarily. That is accepted here because the candidates sharing the newest
# timestamp are identical builds, and any of them only has to run the plugin's companion script.
# Older candidates may be a different patch release, which is why the newest is preferred.
link_newest node /vscode/vscode-server/bin/*/*/node
link_newest codex "$HOME"/.vscode-server/extensions/openai.chatgpt-*/bin/*/codex
EOF
chmod 755 "$helper_tmp"
mv -f "$helper_tmp" "$helper"
"$helper" || true
# zsh is the configured default shell; the guard keeps repeated creates from stacking lines.
# Match the whole line, so an unrelated mention of the helper elsewhere in the file cannot be
# mistaken for the hook and silently suppress it.
hook='"$HOME/.local/bin/link-review-tools" 2>/dev/null'
if [ -e "$HOME/.zshrc" ] && [ ! -f "$HOME/.zshrc" ]; then
    # Reading a FIFO or other special file here would block container creation indefinitely.
    echo "postCreate: $HOME/.zshrc is not a regular file; skipping the shell hook" >&2
elif ! grep -qxF "$hook" "$HOME/.zshrc" 2>/dev/null; then
    # A file whose last line is unterminated would otherwise absorb the hook into that line.
    if [ -s "$HOME/.zshrc" ] && [ "$(tail -c1 "$HOME/.zshrc" | wc -l)" -eq 0 ]; then
        echo >> "$HOME/.zshrc"
    fi
    echo "$hook" >> "$HOME/.zshrc"
fi
fi
