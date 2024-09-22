import glob
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import redis

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.utils import is_url

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
    Retrieve all tasks from the Redis database.
    """
    global redis_client
    try:
        tasks = redis_client.lrange('tasks', 0, -1)
        return [json.loads(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/new", status_code=status.HTTP_201_CREATED)
async def add_tasks(tasks: list[Task]) -> dict:
    """
    Add new tasks to the Redis database.
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
        return {"message": "Tasks added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear")
async def clear_tasks() -> dict:
    """
    Clear all tasks from the Redis queue.
    """
    global redis_client
    try:
        redis_client.delete('tasks')
        return {"message": "All tasks cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
