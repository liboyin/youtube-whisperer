#!/usr/bin/env python3
"""Link the adversarial review harness tools into ``~/.local/bin``.

The review skill drives the ``codex`` CLI through the Codex plugin's companion
scripts, which run under ``node``. Neither is on ``PATH`` in this image: node is
bundled with the VS Code server and codex ships inside the ChatGPT extension,
both behind version-stamped directories. That extension updates far more often
than the devcontainer is rebuilt, so a link resolved once at container creation
goes stale as soon as the plugin updates. This script re-resolves the current
paths, is safe to run repeatedly, and never fails its caller: problems are
reported on stderr so a provisioning run cannot be aborted by a convenience step.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

BIN_DIR = Path.home() / '.local' / 'bin'
VSCODE_SERVER_ROOT = Path('/vscode/vscode-server')
EXTENSIONS_ROOT = Path.home() / '.vscode-server' / 'extensions'

# Tool name -> (root to search, glob relative to that root). Both roots also identify the links
# this script owns, so a link pointing anywhere else is treated as the user's and left alone.
TOOL_GLOBS: dict[str, tuple[Path, str]] = {
    'node': (VSCODE_SERVER_ROOT, 'bin/*/*/node'),
    'codex': (EXTENSIONS_ROOT, 'openai.chatgpt-*/bin/*/codex'),
}


def find_newest_executable(root: Path, pattern: str) -> Path | None:
    """Return the most recently modified regular executable matching a glob.

    Candidates are ordered newest first by modification time and the first
    regular executable file wins, so a partial or corrupt newest install falls
    back to a usable older build instead of leaving the tool unlinked. Newest by
    modification time is a heuristic: builds can share a timestamp and the tie is
    then broken arbitrarily, which is acceptable because candidates sharing the
    newest timestamp are identical builds.

    Args:
        root: Directory the glob is resolved against.
        pattern: Glob relative to ``root``.

    Returns:
        The chosen executable, or ``None`` when nothing usable matches.
    """
    candidates: list[tuple[float, Path]] = []
    try:
        matches = list(root.glob(pattern))
    except OSError:
        return None
    for candidate in matches:
        try:
            candidates.append((candidate.stat().st_mtime, candidate))
        except OSError:  # vanished or unreadable between globbing and inspection
            continue
    for _modified, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_replaceable(destination: Path) -> bool:
    """Report whether a destination may be replaced by a managed link.

    An absent entry is free to claim. An existing entry is replaced only when it
    is a symlink already pointing into one of the tool roots, which is what this
    script creates; that includes a dangling link, the state a plugin update
    leaves behind. A regular file, a directory, a special file, or a link to
    anywhere else belongs to the user and is preserved.

    Args:
        destination: Path in ``~/.local/bin`` that would receive the link.

    Returns:
        ``True`` when writing the link is safe.
    """
    if destination.is_symlink():
        try:
            raw_target = os.readlink(destination)
        except OSError:
            return False
        # Resolve against the link's own directory and collapse any '..' before comparing.
        # Containment is a lexical test, so an unnormalised '<root>/../elsewhere' target would
        # otherwise look owned and let a foreign link be replaced. normpath is used rather than
        # resolve() because the target of a stale link no longer exists.
        target = Path(os.path.normpath(destination.parent / raw_target))
        # Containment must be strict: a link pointing at a root itself is not something this
        # script ever creates, so it belongs to the user and must survive.
        return any(
            target != root and target.is_relative_to(root)
            for root in (VSCODE_SERVER_ROOT, EXTENSIONS_ROOT)
        )
    return not destination.exists()


def link_tool(name: str, root: Path, pattern: str) -> str | None:
    """Point ``~/.local/bin/<name>`` at the newest usable build of one tool.

    The link is swapped in atomically through a temporary name, so a concurrent
    shell never observes the tool missing.

    Args:
        name: Command name to expose in ``~/.local/bin``.
        root: Directory the glob is resolved against.
        pattern: Glob relative to ``root``.

    Returns:
        A diagnostic message when the link could not be created, otherwise
        ``None``, including when nothing matched or the link is already current.
    """
    target = find_newest_executable(root, pattern)
    if target is None:
        return None
    destination = BIN_DIR / name
    if not is_replaceable(destination):
        return f'{destination} is not managed here; leaving it alone'
    if destination.is_symlink() and os.readlink(destination) == str(target):
        return None
    # Stage inside a fresh private directory. A fixed sibling name could collide with something
    # the user owns, and clearing that collision would mean deleting their file.
    try:
        staging_dir = Path(tempfile.mkdtemp(dir=destination.parent))
    except OSError as error:
        return f'could not stage a link for {destination}: {error}'
    try:
        staged = staging_dir / name
        os.symlink(target, staged)
        os.replace(staged, destination)
    except OSError as error:
        return f'could not link {destination}: {error}'
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    return None


def shell_hook_line() -> str:
    """Return the line a shell runs to re-resolve stale links.

    The guard keeps the common case to two cheap tests, so the interpreter only
    starts when a link is actually missing or broken.
    """
    return (
        '[ -x "$HOME/.local/bin/node" ] && [ -x "$HOME/.local/bin/codex" ] '
        f'|| python3 {Path(__file__).resolve()} >/dev/null 2>&1'
    )


def install_shell_hook(rc_path: Path) -> str | None:
    """Add the self-heal hook to a shell startup file unless already present.

    The whole line is matched against LF-delimited lines, the way zsh itself
    splits commands, so an unrelated mention of this script cannot be mistaken
    for the hook. A separating newline is written first when the file
    does not end with one. Anything that is not a regular file is skipped rather
    than written, covering a special file that could block a read and a dangling
    symlink whose target would otherwise be created.

    Args:
        rc_path: Shell startup file to update.

    Returns:
        A diagnostic message when the hook was not installed, otherwise ``None``.
    """
    # lexists rather than exists: a dangling symlink must be skipped too, because appending
    # through it would create its target and write the hook outside the intended path. A symlink
    # that does resolve to a regular file is still followed normally, which is the common case
    # for an rc file kept in a dotfiles repository.
    if os.path.lexists(rc_path) and not rc_path.is_file():
        return f'{rc_path} is not a regular file; skipping the shell hook'
    hook = shell_hook_line()
    # newline='' disables universal-newline translation, so the text keeps the file's real
    # terminators. zsh ends a command at LF only, and matching or terminating on anything else
    # would either miss a hook it cannot see or splice one onto a preceding command.
    try:
        if rc_path.is_file():
            with rc_path.open(encoding='utf-8', newline='') as handle:
                existing = handle.read()
        else:
            existing = ''
    except OSError as error:
        return f'could not read {rc_path}: {error}'
    except UnicodeDecodeError:
        return f'{rc_path} is not valid UTF-8; skipping the shell hook'
    # split on LF only: str.splitlines also breaks on form feed, vertical tab and the Unicode
    # separators, which zsh treats as ordinary characters, so a commented-out hook containing one
    # would otherwise look like a real installed hook.
    if hook in existing.split('\n'):
        return None
    separator = '' if not existing or existing.endswith('\n') else '\n'
    try:
        with rc_path.open('a', encoding='utf-8') as handle:
            handle.write(f'{separator}{hook}\n')
    except OSError as error:
        return f'could not update {rc_path}: {error}'
    return None


def main(argv: list[str]) -> int:
    """Link every known tool and optionally install the shell hook.

    Args:
        argv: Arguments without the program name. ``--install-hook`` additionally
            wires the hook into ``~/.zshrc`` and is meant for container creation.

    Returns:
        Always ``0``. This is a convenience step and must never abort the caller.
    """
    problems: list[str] = []
    # postCreateCommand.sh runs under `set -e`, and linking convenience tools must never be the
    # reason a container fails to build. The specific failures below are reported individually;
    # this outer guard catches anything unforeseen so the exit status stays 0 regardless.
    try:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        for name, (root, pattern) in TOOL_GLOBS.items():
            problem = link_tool(name, root, pattern)
            if problem is not None:
                problems.append(problem)
        if '--install-hook' in argv:
            problem = install_shell_hook(Path.home() / '.zshrc')
            if problem is not None:
                problems.append(problem)
    except Exception as error:  # noqa: BLE001 - the zero-exit contract outranks propagating here
        problems.append(f'unexpected failure: {error!r}')
    try:
        for problem in problems:
            print(f'link_review_tools: {problem}', file=sys.stderr)
    except OSError:
        pass  # a closed or full stderr must not change the exit status either
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
