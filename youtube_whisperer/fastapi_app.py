from contextlib import asynccontextmanager
import glob
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import redis

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, is_url

redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = redis.StrictRedis(host='redis')
        redis_client.ping()
        yield
    finally:
        if redis_client:
            redis_client.close()

app = FastAPI(lifespan=lifespan, title="YouTube Whisperer")


class Task(BaseModel):
    source: str = 'assets/*.mp4'
    language: str = 'en'


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


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
async def add_tasks(tasks: list[Task]) -> list[dict[str, str]]:
    """
    Add new tasks to the Redis queue.
    """
    global redis_client
    try:
        task_dicts: list[dict[str, str]] = []
        for task in tasks:
            if is_url(task.source):
                for url in yield_flattened_video_urls([task.source]):
                    task_dicts.append({"source": url, "language": task.language})
            else:
                for path in glob.glob(os.path.expanduser(task.source)):
                    task_dicts.append({"source": str(path), "language": task.language})
        if task_dicts:
            redis_client.rpush('tasks', *(json.dumps(task) for task in task_dicts))
        return task_dicts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks", status_code=status.HTTP_204_NO_CONTENT)
async def clear_tasks() -> None:
    """
    Clear all tasks from the Redis queue.
    """
    global redis_client
    try:
        redis_client.delete('tasks')
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets")
async def list_assets(dir_path: str = str(WHISPER_ASSETS_DIR)) -> list[str]:
    """
    List all contents of the specified directory.
    """
    try:
        return sorted(map(str, Path(dir_path).iterdir()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
