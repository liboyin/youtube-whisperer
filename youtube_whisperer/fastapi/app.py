from collections import defaultdict
import glob
import os
from pathlib import Path
import shutil
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File
from pathlib_extensions import prepare_input_dir, prepare_output_file
from redis import StrictRedis

from youtube_whisperer.fastapi.models import AddAssetsResponse, AddTasksResponse, DeadLetter, Task, TaskQueues
from youtube_whisperer.queueing import DEAD_LETTER_QUEUE, clear_task_queues, list_dead_letters, list_task_queues, queue_transcription_tasks, queue_youtube_task
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, REDIS_CLIENT, is_url

app = FastAPI(title="YouTube Whisperer")


def get_assets_dir() -> Path:
    return WHISPER_ASSETS_DIR


def get_redis_client() -> Generator[StrictRedis, None, None]:
    yield REDIS_CLIENT


@app.get("/tasks", response_model=TaskQueues)
async def get_tasks(redis_client: StrictRedis = Depends(get_redis_client)) -> TaskQueues:
    """
    Retrieve all pending and active tasks from the Redis queues.
    """
    try:
        return list_task_queues(redis_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def resolve_filesystem_tasks(pattern: Task) -> list[Task]:
    """
    Resolve a filesystem task pattern into a list of concrete Tasks.
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
            failed: Tasks / patterns that failed to resolve
        }
    """
    successful_tasks: list[Task] = []
    failed_tasks: list[Task] = []
    youtube_tasks: list[Task] = []
    transcription_tasks: list[Task] = []
    try:
        for pattern in patterns:
            if is_url(pattern.source):
                successful_tasks.append(pattern)
                youtube_tasks.append(pattern)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks", response_model=TaskQueues)
async def clear_tasks(redis_client: StrictRedis = Depends(get_redis_client)) -> TaskQueues:
    """
    Clear all pending and active tasks from the Redis queues.

    Returns:
        TaskQueues: Snapshot of the deleted tasks.
    """
    try:
        return clear_task_queues(redis_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dead-letters", response_model=list[DeadLetter])
async def get_dead_letters(redis_client: StrictRedis = Depends(get_redis_client)) -> list[DeadLetter]:
    """
    Retrieve failed tasks from the dead-letter queue.
    """
    try:
        return list_dead_letters(redis_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/dead-letters", response_model=list[DeadLetter])
async def clear_dead_letters(redis_client: StrictRedis = Depends(get_redis_client)) -> list[DeadLetter]:
    """
    Clear the dead-letter queue.
    """
    try:
        dead_letters = list_dead_letters(redis_client)
        redis_client.delete(DEAD_LETTER_QUEUE)
        return dead_letters
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets", response_model=list[str])
async def list_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    List all contents of the specified directory.
    """
    try:
        return sorted(map(str, prepare_input_dir(dir_path).rglob("*")))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/assets", response_model=AddAssetsResponse, status_code=status.HTTP_201_CREATED)
async def add_assets(files: list[UploadFile] = File(...), dir_path: Path = Depends(get_assets_dir)) -> AddAssetsResponse:
    """
    Upload files to the asset directory.

    Args:
        files (list[UploadFile]): Files to upload.

    Returns:
        AddAssetsResponse: {
            successful: Saved file paths on the server
            failed: Client-side file paths that failed to upload
        }
    """
    saved_files: list[str] = []
    failed_files: list[str] = []
    try:
        for upload in files:
            assert upload.filename
            target_path = prepare_output_file(dir_path / upload.filename)
            try:
                with target_path.open("wb") as f:
                    shutil.copyfileobj(upload.file, f)
                saved_files.append(str(target_path))
            except Exception:
                failed_files.append(upload.filename)
        return AddAssetsResponse(successful=saved_files, failed=failed_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.delete("/assets", response_model=list[str])
async def clean_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    Clean up redundant files in the specified directory.

    If the same filename exists as MP4 and SRT, remove corresponding MKV/WAV/MP3 files.

    Returns:
        list[str]: List of removed file paths.
    """
    try:
        removed_files: list[str] = []
        for path_without_suffix, suffixes in map_path_to_suffixes(dir_path).items():
            if suffixes >= {'.mp4', '.srt'}:
                for suffix in ('.mkv', '.wav', '.mp3'):
                    if suffix in suffixes and (file_path := Path(f"{path_without_suffix}{suffix}")).is_file():
                        file_path.unlink()
                        removed_files.append(str(file_path))
        return sorted(removed_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
