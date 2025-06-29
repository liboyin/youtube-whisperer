from collections import defaultdict
from contextlib import asynccontextmanager
import datetime
import glob
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, get_redis_client, is_url

redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = get_redis_client()
        yield
    finally:
        if redis_client:
            redis_client.close()

app = FastAPI(lifespan=lifespan, title="YouTube Whisperer")


class Task(BaseModel):
    source: str = f'assets/{datetime.date.today().year}*.mkv'
    language: str = 'en'


class AddTasksResponse(BaseModel):
    successful: list[Task]
    failed: list[Task]


@app.get("/tasks")
async def get_tasks() -> list[Task]:
    """
    Retrieve all tasks from the Redis queue.
    """
    global redis_client
    try:
        tasks = redis_client.lrange('tasks', 0, -1)
        return [json.loads(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def resolve_tasks(pattern: Task) -> list[Task]:
    """
    Resolve a Task pattern into a list of concrete Tasks.
    """
    result: list[Task] = []
    if is_url(pattern.source):
        for url in yield_flattened_video_urls([pattern.source]):
            result.append(Task(source=url, language=pattern.language))
    else:
        for path in glob.glob(os.path.expanduser(pattern.source)):
            result.append(Task(source=str(path), language=pattern.language))
    return result


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
async def add_tasks(patterns: list[Task]) -> AddTasksResponse:
    """
    Add new tasks from patterns to the Redis queue.

    Args:
        patterns (list[Task]): List of task patterns.

    Returns:
        AddTasksResponse:
            - A list of tasks that have been successfully added to the work queue
            - A list of tasks or patterns that failed to resolve
    """
    global redis_client
    try:
        successful_tasks: list[Task] = []
        failed_tasks: list[Task] = []
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
async def clear_tasks() -> list[Task]:
    """
    Clear all tasks from the Redis queue.

    Returns:
        list[Task]: List of tasks that were deleted from the queue.
    """
    global redis_client
    try:
        deleted = [Task.model_validate_json(task) for task in redis_client.lrange('tasks', 0, -1)]
        redis_client.delete('tasks')
        return deleted
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets")
async def list_assets(dir_path: Path = WHISPER_ASSETS_DIR) -> list[str]:
    """
    List all contents of the specified directory.
    """
    try:
        return sorted(map(str, dir_path.iterdir()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/assets")
async def clean_assets(dir_path: Path = WHISPER_ASSETS_DIR) -> list[str]:
    """
    Clean up redundant files in the specified directory.

    If the same filename exists as MP4 and SRT, remove corresponding MKV and SEG files.

    Args:
        dir_path (Path): The directory path to clean up.

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
