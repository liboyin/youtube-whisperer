import glob
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

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


@app.put("/assets_in")
async def assets_in() -> dict:
    """
    Move all 2024*.mp4 files from ~/.whisper/Transcode to ~/.whisper.
    """
    source_dir = Path.home() / ".whisper" / "Transcode"
    dest_dir = Path.home() / ".whisper"
    try:
        for file_path in source_dir.glob("2024*.mp4"):
            dest_path = dest_dir / file_path.name
            if not dest_path.exists():
                file_path.rename(dest_path)
        return {"message": "Assets moved in successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/assets_out")
async def assets_out() -> dict:
    """
    Move all *.mp4 and *.srt files from ~/.whisper to ~/.whisper/Transcode. Delete all *.seg files from ~/.whisper.
    """
    source_dir = Path.home() / ".whisper"
    dest_dir = Path.home() / ".whisper" / "Transcode"
    try:
        # move .mp4 and .srt files
        for file_path in source_dir.glob("*.[ms][pr][t4]"):
            dest_path = dest_dir / file_path.name
            if not dest_path.exists():
                file_path.rename(dest_path)
        # delete .seg files
        for seg_file in source_dir.glob("*.seg"):
            seg_file.unlink()
        return {"message": "Assets moved out successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
