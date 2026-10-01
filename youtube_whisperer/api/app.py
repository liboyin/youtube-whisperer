import glob
import logging
import os
from collections import defaultdict
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pathlib_extensions import prepare_input_dir
from redis import ConnectionPool, StrictRedis

from youtube_whisperer.config import Settings
from youtube_whisperer.domain import TranscriberType, is_url
from youtube_whisperer.models import AddTasksResponse, DeadLetter, Task, TaskQueues
from youtube_whisperer.queueing import (
    DEAD_LETTER_QUEUE,
    clear_task_queues,
    list_dead_letters,
    list_task_queues,
    queue_transcription_tasks,
    queue_youtube_task,
)
from youtube_whisperer.runtime import Runtime

logger = logging.getLogger(__name__)

# FastAPI requires a concrete Request annotation; None retains standalone calls.
_NO_REQUEST = cast(Request, None)
router = APIRouter()


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


def get_assets_dir(request: Request = _NO_REQUEST) -> Path:
    """FastAPI dependency that supplies the configured asset directory.

    Args:
        request: Request whose app owns the snapshot; omitted for standalone access.

    Returns:
        Path: The root directory used as the media library.
    """
    application = request.app if request is not None else app
    runtime = getattr(application.state, 'runtime', None)
    return runtime.assets_dir if runtime is not None else Settings().whisper_assets_dir


def get_redis_client(request: Request = _NO_REQUEST) -> Generator[StrictRedis, None, None]:
    """FastAPI dependency that supplies the shared, pooled Redis client.

    Args:
        request: Request whose app owns resources; omitted for standalone access.

    Yields:
        StrictRedis: Runtime client, or an invocation-owned client closed after yielding.
    """
    application = request.app if request is not None else app
    runtime = getattr(application.state, 'runtime', None)
    if runtime is not None:
        yield runtime.client
    else:
        with Runtime() as runtime:
            yield runtime.client


RedisClientDep = Annotated[StrictRedis, Depends(get_redis_client)]
AssetsDirDep = Annotated[Path, Depends(get_assets_dir)]


@router.get("/tasks", response_model=TaskQueues)
async def get_tasks(redis_client: RedisClientDep) -> TaskQueues:
    """
    Retrieve all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: A snapshot of every routing stream partitioned into pending and active tasks.
    """
    return list_task_queues(redis_client)


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


@router.post("/tasks", response_model=AddTasksResponse, status_code=status.HTTP_201_CREATED)
async def add_tasks(patterns: list[Task], redis_client: RedisClientDep) -> AddTasksResponse:
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


@router.delete("/tasks", response_model=TaskQueues)
async def clear_tasks(redis_client: RedisClientDep) -> TaskQueues:
    """
    Clear all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: Snapshot of the deleted tasks.
    """
    return clear_task_queues(redis_client)


@router.get("/dead-letters", response_model=list[DeadLetter])
async def get_dead_letters(redis_client: RedisClientDep) -> list[DeadLetter]:
    """
    Retrieve failed tasks from the dead-letter queue.

    Returns:
        list[DeadLetter]: Every dead-lettered task in insertion order.
    """
    return list_dead_letters(redis_client)


@router.delete("/dead-letters", response_model=list[DeadLetter])
async def clear_dead_letters(redis_client: RedisClientDep) -> list[DeadLetter]:
    """
    Clear the dead-letter queue.

    Returns:
        list[DeadLetter]: The dead-lettered tasks that were removed.
    """
    dead_letters = list_dead_letters(redis_client)
    redis_client.delete(DEAD_LETTER_QUEUE)
    return dead_letters


@router.get("/assets", response_model=list[str])
async def list_assets(dir_path: AssetsDirDep) -> list[str]:
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


@router.delete("/assets", response_model=list[str])
async def clean_assets(dir_path: AssetsDirDep) -> list[str]:
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


def create_app(
    settings: Settings | None = None,
    client: StrictRedis | None = None,
    *,
    pool: ConnectionPool | None = None,
    owns_pool: bool = False,
) -> FastAPI:
    """Create an API whose lifespan owns one snapshot and its Redis resources.

    Args:
        settings: Supplied snapshot; None resolves environment at lifespan startup.
        client: Borrowed client that lifespan must not close.
        pool: Supplied pool, borrowed unless ownership is transferred.
        owns_pool: Whether lifespan must disconnect a supplied pool.

    Returns:
        An independent application with the established routes and error handling.
    """
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Bind resources at startup and release ownership even on interruption."""
        with Runtime(settings, client, pool=pool, owns_pool=owns_pool) as runtime:
            application.state.runtime = runtime
            try:
                yield
            finally:
                del application.state.runtime

    application = FastAPI(title="YouTube Whisperer", lifespan=lifespan)
    application.add_exception_handler(Exception, handle_unexpected_exception)
    application.include_router(router)
    return application


app = create_app()
