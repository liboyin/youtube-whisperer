import json
import time

from youtube_whisperer.utils import redis_connection


def process_queue():
    with redis_connection() as client:
        while True:
            task = client.lindex('tasks', 0)
            if task:
                source, language = json.loads(task)
                print(f"Processing task: {source}, {language}")
                client.lpop('tasks')
            else:
                print("Queue is empty")
                time.sleep(60)


if __name__ == "__main__":
    process_queue()
