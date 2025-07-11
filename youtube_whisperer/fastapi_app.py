from collections import defaultdict
import datetime
import glob
import os
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, field_validator
from redis import StrictRedis

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, WHISPER_LANG_CODES, WhisperMode, get_redis_client, is_url


def get_redis() -> Generator[StrictRedis, None, None]:
    client = get_redis_client()
    try:
        yield client
    finally:
        if client:
            client.close()


app = FastAPI(title="YouTube Whisperer")


class Task(BaseModel):
    """
    source: str
        At input time, source can be a URL of a YouTube video or a playlist, or a glob pattern for local files.
        After resolution, it will be a concrete URL of a YouTube video or a local file path.

    language: str
        The language code for the transcription. Must be one of Whisper-supported language codes.

    mode: WhisperMode
        Whether to run Whisper in transcribe mode or translate mode.
    """
    source: str = f'assets/{datetime.date.today().year}*.mkv'
    language: str = 'en'
    mode: WhisperMode = WhisperMode.TRANSCRIBE

    @field_validator('source')
    def validate_source(cls, x: str) -> str:
        if not x.strip():
            raise ValueError('Source cannot be empty')
        return x.strip()

    @field_validator('language')
    def validate_language(cls, x: str) -> str:
        if not x or x not in WHISPER_LANG_CODES:
            raise ValueError(f'Unsupported language: {x}')
        return x

    @field_validator('mode')
    def validate_mode(cls, x: str | WhisperMode) -> WhisperMode:
        if isinstance(x, WhisperMode):
            return x
        if isinstance(x, str):
            return WhisperMode(x)
        raise TypeError(f'Unexpected WhisperMode {x} of type {type(x)}')


class AddTasksResponse(BaseModel):
    successful: list[Task]
    failed: list[Task]


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
        AddTasksResponse:
            - A list of tasks that have been successfully added to the work queue
            - A list of tasks or patterns that failed to resolve
    """
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
