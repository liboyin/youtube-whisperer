from collections import defaultdict
import glob
import os
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File
from pathlib_extensions import prepare_output_file
from redis import StrictRedis

from youtube_whisperer.fastapi.models import Task, AddTasksResponse, AddAssetsResponse
from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, get_redis_client, is_url

app = FastAPI(title="YouTube Whisperer")


def get_redis() -> Generator[StrictRedis, None, None]:
    client = get_redis_client()
    try:
        yield client
    finally:
        if client:
            client.close()


def get_assets_dir() -> Path:
    return WHISPER_ASSETS_DIR


@app.get("/tasks")
async def get_tasks(redis_client: StrictRedis = Depends(get_redis)) -> list[Task]:
    """
    Retrieve all tasks from the Redis queue.
    """
    try:
        tasks = redis_client.lrange('tasks', 0, -1)
        return [Task.model_validate_json(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def resolve_tasks(pattern: Task) -> list[Task]:
    """
    Resolve a Task pattern into a list of concrete Tasks.
    """
    result: list[Task] = []
    if is_url(pattern.source):
        for url in yield_flattened_video_urls([pattern.source]):
            result.append(Task(source=url, language=pattern.language, mode=pattern.mode))
    else:
        for path in glob.glob(os.path.expanduser(pattern.source)):
            result.append(Task(source=str(path), language=pattern.language, mode=pattern.mode))
    return result


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
async def add_tasks(patterns: list[Task], redis_client: StrictRedis = Depends(get_redis)) -> AddTasksResponse:
    """
    Add new tasks from patterns to the Redis queue.

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
    try:
        for pattern in patterns:
            if resolved_tasks := resolve_tasks(pattern):
                successful_tasks.extend(resolved_tasks)
            else:
                failed_tasks.append(pattern)
        if successful_tasks:
            redis_client.rpush('tasks', *(task.model_dump_json() for task in successful_tasks))
        return AddTasksResponse(successful=successful_tasks, failed=failed_tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks")
async def clear_tasks(redis_client: StrictRedis = Depends(get_redis)) -> list[Task]:
    """
    Clear all tasks from the Redis queue.

    Returns:
        list[Task]: List of tasks that were deleted from the queue.
    """
    try:
        deleted = [Task.model_validate_json(task) for task in redis_client.lrange('tasks', 0, -1)]
        redis_client.delete('tasks')
        return deleted
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets")
async def list_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    List all contents of the specified directory.
    """
    try:
        return sorted(map(str, dir_path.iterdir()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/assets", status_code=status.HTTP_201_CREATED)
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
            target_path = prepare_output_file(dir_path / upload.filename)
            try:
                with target_path.open("wb") as f:
                    content = await upload.read()
                    f.write(content)
                saved_files.append(str(target_path))
            except Exception:
                failed_files.append(upload.filename)
        return AddAssetsResponse(successful=saved_files, failed=failed_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/assets")
async def clean_assets(dir_path: Path = Depends(get_assets_dir)) -> list[str]:
    """
    Clean up redundant files in the specified directory.

    If the same filename exists as MP4 and SRT, remove corresponding MKV and SEG files.

    Returns:
        list[str]: List of removed file paths.
    """
    try:
        stem2suffixes: dict[str, set[str]] = defaultdict(set)
        for file_path in dir_path.iterdir():
            if file_path.is_file():
                stem2suffixes[file_path.stem].add(file_path.suffix.lower())
        removed_files: list[str] = []
        for stem, suffixes in stem2suffixes.items():
            if suffixes >= {'.mp4', '.srt'}:
                for suffix in ['.mkv', '.seg', '.mp3']:
                    if suffix in suffixes and (file_path := dir_path / f"{stem}{suffix}").is_file():
                        file_path.unlink()
                        removed_files.append(str(file_path))
        return sorted(removed_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
