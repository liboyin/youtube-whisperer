from collections import defaultdict
import glob
import logging
import os
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pathlib_extensions import prepare_input_dir
from redis import StrictRedis

from youtube_whisperer.models import AddTasksResponse, DeadLetter, Task, TaskQueues
from youtube_whisperer.queueing import DEAD_LETTER_QUEUE, clear_task_queues, list_dead_letters, list_task_queues, queue_transcription_tasks, queue_youtube_task
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, REDIS_CLIENT, TranscriberType, is_url

logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Whisperer")


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """Convert any uncaught exception into a sanitized 500 response.

    The full traceback is logged via `logger.exception` so operators can debug; the response
    body intentionally omits the original exception message to avoid leaking internal details
    (connection strings, file paths, secrets) to clients.

    Args:
        request: The incoming request that triggered the exception.
        exc: The unhandled exception raised inside the endpoint.

    Returns:
        A 500 `JSONResponse` with a generic error detail.
    """
    logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def get_assets_dir() -> Path:
    """FastAPI dependency that supplies the configured asset directory.

    Returns:
        Path: The root directory used as the media library.
    """
    return WHISPER_ASSETS_DIR


def get_redis_client() -> Generator[StrictRedis, None, None]:
    """FastAPI dependency that supplies the shared, pooled Redis client.

    Yields:
        StrictRedis: The process-wide Redis client backed by a connection pool.
    """
    yield REDIS_CLIENT


@app.get("/tasks", response_model=TaskQueues)
async def get_tasks(redis_client: StrictRedis = Depends(get_redis_client)) -> TaskQueues:
    """
    Retrieve all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: A snapshot of every routing stream partitioned into pending and active tasks.
    """
    return list_task_queues(redis_client)


def resolve_filesystem_tasks(pattern: Task) -> list[Task]:
    """
    Resolve a filesystem task pattern into a list of concrete Tasks.

    Args:
        pattern (Task): A task whose `source` is a glob pattern over the local filesystem.

    Returns:
        list[Task]: One copy of `pattern` per matched file, with `source` set to that file path.
    """
    return [pattern.model_copy(update={'source': str(path)}) for path in glob.glob(os.path.expanduser(pattern.source))]


@app.post("/tasks", response_model=AddTasksResponse, status_code=status.HTTP_201_CREATED)
async def add_tasks(patterns: list[Task], redis_client: StrictRedis = Depends(get_redis_client)) -> AddTasksResponse:
    """
    Add new tasks to the appropriate Redis queues.

    Args:
        patterns (list[Task]): List of task patterns.

    Returns:
        AddTasksResponse: {
            successful: Tasks that have been successfully added to the work queue
            failed: Tasks / patterns that were not actionable: a filesystem pattern that
                matched no files, or a filesystem source with the `none` transcriber
                (which only applies to downloadable URL sources)
        }
    """
    successful_tasks: list[Task] = []
    failed_tasks: list[Task] = []
    youtube_tasks: list[Task] = []
    transcription_tasks: list[Task] = []
    for pattern in patterns:
        if is_url(pattern.source):
            successful_tasks.append(pattern)
            youtube_tasks.append(pattern)
        elif pattern.transcriber == TranscriberType.NONE:
            # `none` means "download only"; a local file has nothing to download and, without
            # transcription, no output would be produced, so the task is not actionable.
            failed_tasks.append(pattern)
        elif resolved_tasks := resolve_filesystem_tasks(pattern):
            successful_tasks.extend(resolved_tasks)
            transcription_tasks.extend(resolved_tasks)
        else:
            failed_tasks.append(pattern)
    for task in youtube_tasks:
        queue_youtube_task(redis_client, task)
    if transcription_tasks:
        queue_transcription_tasks(redis_client, transcription_tasks)
    return AddTasksResponse(successful=successful_tasks, failed=failed_tasks)


@app.delete("/tasks", response_model=TaskQueues)
async def clear_tasks(redis_client: StrictRedis = Depends(get_redis_client)) -> TaskQueues:
    """
    Clear all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: Snapshot of the deleted tasks.
    """
    return clear_task_queues(redis_client)


@app.get("/dead-letters", response_model=list[DeadLetter])
async def get_dead_letters(redis_client: StrictRedis = Depends(get_redis_client)) -> list[DeadLetter]:
    """
    Retrieve failed tasks from the dead-letter queue.

    Returns:
        list[DeadLetter]: Every dead-lettered task in insertion order.
    """
    return list_dead_letters(redis_client)


@app.delete("/dead-letters", response_model=list[DeadLetter])
async def clear_dead_letters(redis_client: StrictRedis = Depends(get_redis_client)) -> list[DeadLetter]:
    """
    Clear the dead-letter queue.

    Returns:
        list[DeadLetter]: The dead-lettered tasks that were removed.
    """
    dead_letters = list_dead_letters(redis_client)
    redis_client.delete(DEAD_LETTER_QUEUE)
    return dead_letters


@app.get("/assets", response_model=list[str])
async def list_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    List all contents of the specified directory.

    Returns:
        list[str]: Sorted paths of every entry found recursively under the asset directory.
    """
    return sorted(map(str, prepare_input_dir(dir_path).rglob("*")))


def map_path_to_suffixes(dir_path: Path) -> dict[str, set[str]]:
    """Recursively maps each file path without suffix to the set of lowercased suffixes under dir_path.

    Args:
        dir_path: Root directory to scan. Must exist.

    Returns:
        A dict mapping each file path without suffix to the set of lowercased suffixes found across all
        files under dir_path (e.g. ``{"parent/video": {".mp4", ".srt"}}``).

    Raises:
        Exception: If dir_path does not exist or is not accessible.
    """
    stem2suffixes: dict[str, set[str]] = defaultdict(set)
    for file_path in prepare_input_dir(dir_path).rglob("*"):
        if file_path.is_file():
            stem2suffixes[str(file_path.with_suffix(''))].add(file_path.suffix.lower())
    return dict(stem2suffixes)


def redundant_media_paths(stem_to_suffixes: dict[str, set[str]]) -> list[Path]:
    """Select transient media files made redundant by a finished MP4 + SRT pair.

    A path stem is treated as complete only when both an ``.mp4`` and an ``.srt``
    file exist for it; its source ``.mkv``/``.wav``/``.mp3`` siblings are then
    redundant. The MP4 and SRT themselves are never selected.

    Args:
        stem_to_suffixes: Mapping of each path without suffix to the set of
            lowercased suffixes present for it (see ``map_path_to_suffixes``).

    Returns:
        list[Path]: Paths of redundant media files, in arbitrary order.
    """
    redundant: list[Path] = []
    for stem, suffixes in stem_to_suffixes.items():
        if suffixes >= {'.mp4', '.srt'}:
            redundant.extend(Path(f"{stem}{suffix}") for suffix in ('.mkv', '.wav', '.mp3') if suffix in suffixes)
    return redundant


@app.delete("/assets", response_model=list[str])
async def clean_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    Clean up redundant files in the specified directory.

    If the same filename exists as MP4 and SRT, remove corresponding MKV/WAV/MP3 files.

    Returns:
        list[str]: List of removed file paths.
    """
    removed_files: list[str] = []
    for file_path in redundant_media_paths(map_path_to_suffixes(dir_path)):
        if file_path.is_file():
            file_path.unlink()
            removed_files.append(str(file_path))
    return sorted(removed_files)
