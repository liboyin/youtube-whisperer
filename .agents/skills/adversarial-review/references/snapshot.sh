#! /bin/bash
# Print the review integrity snapshot that the adversarial review skill's step 1 requires: HEAD, porcelain status
# (which lists out-of-scope untracked paths by name only), and the mode plus SHA-256 or symlink target of every
# tracked path that differs from HEAD (staged or unstaged) and every named in-scope untracked file. Ignored content
# is never read: a named path that is tracked, ignored, a directory, or outside the repository is rejected.
#
# Usage: snapshot.sh [in-scope-untracked-file...] > before.txt
#        snapshot.sh [same files...] | diff before.txt -    # empty diff and exit 0 means unchanged
# Paths are relative to the repository root. --no-renames keeps both sides of a rename in the entries.
# Run from anywhere inside the repository.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

for path in "$@"; do
    # Exact match against Git's own untracked, non-ignored listing; a directory lists its children instead.
    listed="$(git --literal-pathspecs ls-files -z --others --exclude-standard -- "$path" 2>/dev/null | tr -d '\0' || true)"
    if [ "$listed" != "$path" ] || { [ ! -f "$path" ] && [ ! -L "$path" ]; }; then
        echo "snapshot: not an in-scope untracked file (tracked, ignored, missing, directory or outside the repository): $path" >&2
        exit 2
    fi
done

echo "HEAD $(git rev-parse HEAD)"
echo "## status"
git status --porcelain=v1 --untracked-files=all
echo "## entries"
{ git diff -z --name-only --no-renames HEAD; [ "$#" -eq 0 ] || printf '%s\0' "$@"; } | sort -zu | while IFS= read -r -d '' path; do
    if [ -L "$path" ]; then
        # Record the link itself; never follow it, since it may point outside the repository.
        echo "symlink $path -> $(readlink -- "$path")"
    elif [ -f "$path" ]; then
        echo "file $(stat -c %a -- "$path") $(sha256sum < "$path" | cut -d' ' -f1) $path"
    else
        echo "absent $path"
    fi
done
