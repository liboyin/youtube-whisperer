from contextlib import asynccontextmanager
import glob
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel
import redis

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import WHISPER_HOME_DIR, is_url

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

app = FastAPI(lifespan=lifespan)


class Task(BaseModel):
    source: str
    language: str


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
async def add_tasks(tasks: list[Task]) -> list[Task]:
    """
    Add new tasks to the Redis queue.
    """
    global redis_client
    try:
        task_jsons = []
        for task in tasks:
            if is_url(task.source):
                for url in yield_flattened_video_urls([task.source]):
                    task_jsons.append(json.dumps({"source": url, "language": task.language}))
            else:
                for path in glob.glob(os.path.expanduser(task.source)):
                    task_jsons.append(json.dumps({"source": str(path), "language": task.language}))
        if task_jsons:
            redis_client.rpush('tasks', *task_jsons)
        return task_jsons
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
async def list_assets(dir_path: str = str(WHISPER_HOME_DIR)) -> list[str]:
    """
    List all contents of the specified directory.
    """
    try:
        return sorted(map(str, Path(dir_path).iterdir()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/assets", status_code=status.HTTP_201_CREATED)
async def move_assets(direction: str = Query(..., enum=["in", "out"])) -> dict:
    """
    Execute `./mvassets.sh in` or `./mvassets.sh out`.
    """
    try:
        result = os.system(f"./mvassets.sh {direction}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result != 0:
        raise HTTPException(status_code=500, detail=f"Failed to move assets {direction}")
    return {"message": f"Assets moved {direction} successfully"}
