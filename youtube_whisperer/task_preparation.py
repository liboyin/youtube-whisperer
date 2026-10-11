"""Prepare submitted task patterns for queue routing, without HTTP or Redis.

Importing this module constructs no settings or Redis resources and loads neither FastAPI nor
Redis; it depends only on the domain classifier and task models.
"""

import glob
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from youtube_whisperer.domain import TranscriberType, is_url
from youtube_whisperer.models import Task


@dataclass(frozen=True)
class PreparedTasks:
    """Immutable outcome of preparing one task submission.

    Attributes:
        successful: Actionable tasks in input order, each filesystem pattern replaced by its
            resolved file tasks in glob order.
        failed: Patterns that were not actionable, in input order.
        youtube: URL tasks to submit to the YouTube stream, in input order.
        transcription: Resolved filesystem tasks to submit for transcription, in input and
            expansion order.
    """

    successful: tuple[Task, ...]
    failed: tuple[Task, ...]
    youtube: tuple[Task, ...]
    transcription: tuple[Task, ...]


def resolve_filesystem_tasks(pattern: Task) -> list[Task]:
    """Resolve a filesystem pattern into absolute file tasks in glob order.

    Paths are anchored to the API working directory without resolving symlink aliases.
    File symlinks are retained; directories and other non-file matches are skipped.

    Args:
        pattern (Task): A task whose `source` is a glob pattern over the local filesystem.

    Returns:
        list[Task]: One copy of `pattern` per matched file, with `source` set to that file path.
    """
    return [
        pattern.model_copy(update={'source': str(Path(path).absolute())})
        for path in glob.glob(os.path.expanduser(pattern.source))
        if Path(path).is_file()
    ]


def prepare_tasks(patterns: Iterable[Task]) -> PreparedTasks:
    """Classify submitted patterns and resolve filesystem sources without submitting anything.

    URL sources are routed to the YouTube stream unchanged, including download-only `none` tasks.
    A filesystem source with the `none` transcriber is failed without being resolved: a local
    file has nothing to download and, without transcription, no output would be produced.
    Other filesystem patterns are expanded by `resolve_filesystem_tasks`; a pattern matching no
    files is failed. Expansion reads the local filesystem relative to the working directory.

    Args:
        patterns: Submitted task patterns, in request order.

    Returns:
        PreparedTasks: The response bookkeeping and the routing lists for submission.
    """
    successful: list[Task] = []
    failed: list[Task] = []
    youtube: list[Task] = []
    transcription: list[Task] = []
    for pattern in patterns:
        if is_url(pattern.source):
            successful.append(pattern)
            youtube.append(pattern)
        elif pattern.transcriber == TranscriberType.NONE:
            failed.append(pattern)
        elif resolved_tasks := resolve_filesystem_tasks(pattern):
            successful.extend(resolved_tasks)
            transcription.extend(resolved_tasks)
        else:
            failed.append(pattern)
    return PreparedTasks(tuple(successful), tuple(failed), tuple(youtube), tuple(transcription))
