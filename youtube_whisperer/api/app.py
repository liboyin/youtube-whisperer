import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Collection, Generator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pathlib_extensions import prepare_input_dir
from redis import ConnectionPool, StrictRedis
from starlette.concurrency import run_in_threadpool

from youtube_whisperer import task_preparation
from youtube_whisperer.config import Settings
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
# Forward the same object for existing `api.app.resolve_filesystem_tasks` imports (D42).
resolve_filesystem_tasks = task_preparation.resolve_filesystem_tasks

# FastAPI requires a concrete Request annotation; None retains standalone calls.
_NO_REQUEST = cast(Request, None)
# Endpoints stay coroutine functions (D18) but run their blocking Redis and filesystem work in
# the threadpool with one offload per request, so a stalled call does not stall the event loop.
router = APIRouter()
# Lowercase suffixes of a finished stem, and of the transient media it makes redundant.
COMPLETED_MEDIA_SUFFIXES = frozenset({'.mp4', '.srt'})
TRANSIENT_MEDIA_SUFFIXES = frozenset({'.mkv', '.wav', '.mp3'})


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
    return await run_in_threadpool(list_task_queues, redis_client)


def submit_tasks(patterns: list[Task], redis_client: StrictRedis) -> AddTasksResponse:
    """Prepare task patterns and submit the actionable ones, blocking on filesystem and Redis I/O.

    URL tasks are submitted one at a time in input order before one bulk submission of resolved
    filesystem tasks. Submission is best-effort (D11): a failure propagates after earlier
    submissions were made.

    Args:
        patterns: Submitted task patterns, in request order.
        redis_client: Client used for submission.

    Returns:
        AddTasksResponse: Successful tasks in input/expansion order and non-actionable patterns.
    """
    prepared = task_preparation.prepare_tasks(patterns)
    for task in prepared.youtube:
        queue_youtube_task(redis_client, task)
    if prepared.transcription:
        queue_transcription_tasks(redis_client, list(prepared.transcription))
    return AddTasksResponse(successful=list(prepared.successful), failed=list(prepared.failed))


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
    return await run_in_threadpool(submit_tasks, patterns, redis_client)


@router.delete("/tasks", response_model=TaskQueues)
async def clear_tasks(redis_client: RedisClientDep) -> TaskQueues:
    """
    Clear all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: Snapshot of the deleted tasks.
    """
    return await run_in_threadpool(clear_task_queues, redis_client)


@router.get("/dead-letters", response_model=list[DeadLetter])
async def get_dead_letters(redis_client: RedisClientDep) -> list[DeadLetter]:
    """
    Retrieve failed tasks from the dead-letter queue.

    Returns:
        list[DeadLetter]: Every dead-lettered task in insertion order.
    """
    return await run_in_threadpool(list_dead_letters, redis_client)


def delete_dead_letters(redis_client: StrictRedis) -> list[DeadLetter]:
    """Read and then delete the dead-letter queue, blocking on Redis I/O.

    The read and delete are not atomic (D9): a concurrent append may be removed unreported.

    Args:
        redis_client: Client owning the dead-letter queue.

    Returns:
        list[DeadLetter]: The entries read before deletion.
    """
    dead_letters = list_dead_letters(redis_client)
    redis_client.delete(DEAD_LETTER_QUEUE)
    return dead_letters


@router.delete("/dead-letters", response_model=list[DeadLetter])
async def clear_dead_letters(redis_client: RedisClientDep) -> list[DeadLetter]:
    """
    Clear the dead-letter queue.

    Returns:
        list[DeadLetter]: The dead-lettered tasks that were removed.
    """
    return await run_in_threadpool(delete_dead_letters, redis_client)


def sorted_asset_paths(dir_path: Path) -> list[str]:
    """List every entry recursively under dir_path, blocking on directory traversal.

    Args:
        dir_path: Root directory to list. Must exist.

    Returns:
        list[str]: Sorted paths of every file and directory found.
    """
    return sorted(map(str, prepare_input_dir(dir_path).rglob("*")))


@router.get("/assets", response_model=list[str])
async def list_assets(dir_path: AssetsDirDep) -> list[str]:
    """
    List all contents of the specified directory.

    Returns:
        list[str]: Sorted paths of every entry found recursively under the asset directory.
    """
    return await run_in_threadpool(sorted_asset_paths, dir_path)


def group_files_by_stem(dir_path: Path) -> dict[Path, list[Path]]:
    """Recursively group the actual files under dir_path by their exact path without suffix.

    File symlinks are included; directories and broken symlinks are skipped. Paths keep their
    on-disk spelling, so case variants such as ``video.wav`` and ``video.WAV`` stay distinct.

    Args:
        dir_path: Root directory to scan. Must exist.

    Returns:
        A dict mapping each path without suffix to the files sharing it, in scan order
        (e.g. ``{Path("parent/video"): [Path("parent/video.MP4"), Path("parent/video.srt")]}``).

    Raises:
        Exception: If dir_path does not exist or is not accessible.
    """
    files_by_stem: dict[Path, list[Path]] = defaultdict(list)
    for file_path in prepare_input_dir(dir_path).rglob("*"):
        if file_path.is_file():
            files_by_stem[file_path.with_suffix('')].append(file_path)
    return dict(files_by_stem)


def redundant_media_paths(files_by_stem: Mapping[Path, Collection[Path]]) -> list[Path]:
    """Select transient media files made redundant by a finished MP4 + SRT pair.

    A path stem is complete only when its files include an ``.mp4`` and an ``.srt``;
    its ``.mkv``/``.wav``/``.mp3`` files are then redundant. Suffixes match
    case-insensitively, while selected paths are returned exactly as supplied, so
    every case variant is selected. The MP4 and SRT themselves are never selected.

    Args:
        files_by_stem: Mapping of each path without suffix to its actual files
            (see ``group_files_by_stem``).

    Returns:
        list[Path]: The supplied paths of redundant media files, in arbitrary order.
    """
    redundant: list[Path] = []
    for files in files_by_stem.values():
        if {path.suffix.lower() for path in files} >= COMPLETED_MEDIA_SUFFIXES:
            redundant.extend(path for path in files if path.suffix.lower() in TRANSIENT_MEDIA_SUFFIXES)
    return redundant


def remove_redundant_media(dir_path: Path) -> list[str]:
    """Delete redundant transient media under dir_path, blocking on traversal and deletion.

    A selected file that is already gone when it is deleted, for example because a concurrent
    request removed it first, is skipped and not reported; any other deletion error propagates.

    Args:
        dir_path: Root directory to clean. Must exist.

    Returns:
        list[str]: Sorted actual paths of the files this call removed.
    """
    removed_files: list[str] = []
    for file_path in redundant_media_paths(group_files_by_stem(dir_path)):
        try:
            file_path.unlink()
        except FileNotFoundError:
            continue
        removed_files.append(str(file_path))
    return sorted(removed_files)


@router.delete("/assets", response_model=list[str])
async def clean_assets(dir_path: AssetsDirDep) -> list[str]:
    """
    Clean up redundant files in the specified directory.

    If the same path without suffix exists as MP4 and SRT, remove its MKV/WAV/MP3 files,
    matching suffixes case-insensitively. A selected file that is already gone when this
    request deletes it is skipped and not reported; any other deletion error propagates.

    Returns:
        list[str]: Sorted actual paths of the files this request removed.
    """
    return await run_in_threadpool(remove_redundant_media, dir_path)


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
