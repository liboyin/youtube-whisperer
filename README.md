# YouTube Whisperer

## Overview

`youtube-whisperer` is a Python application that downloads YouTube videos and transcribes video files into SRT subtitle files, served via a RESTful API.

## Features

- **Download:** YouTube videos, playlists, and existing transcripts in a user-specified language.
- **Transcribe:** Generate SRT subtitle files from local video/audio files.
- **Local transcriber:** `faster-whisper` on a local NVIDIA GPU or CPU. Default model is `large-v3` (~9 GB RAM/VRAM). Runs synchronously.
- **Cloud transcriber:** Azure AI Speech Services, called asynchronously in a thread pool.
- **Task queue:** Redis-backed asynchronous task scheduling.
- **Containerization:** Docker Compose with GPU and CPU support.

## Tech Stack

- Backend: Python + FastAPI
- Transcription: `faster-whisper` (local), `azure-cognitiveservices-speech` (cloud)
- YouTube: `yt-dlp`, `youtube-transcript-api`
- Video/Audio: ffmpeg
- Task Queue: Redis
- Containerization: Docker Compose

## Architecture

Three main components:

1. **REST API** — Exposes endpoints for managing tasks and assets. Resolves file patterns and expands YouTube playlists to individual URLs before enqueuing tasks in Redis.
2. **Worker** — Consumes tasks from Redis, downloads videos and transcripts, routes to the appropriate transcription engine for files without a corresponding transcript file, and writes `.srt` output.
3. **Redis** — Task queue shared between the API and worker.

## Data Flow

1. User submits a task via CLI or REST API, specifying the transcriber (`local` or `azure`) and language.
2. The API resolves file patterns and expands playlists, then enqueues the task in Redis.
3. A worker picks up the task.
4. For URLs, the worker first attempts to fetch a pre-existing transcript; if unavailable, it downloads the video/audio.
5. The transcription engine processes the audio and an adaptor converts the output to an `.srt` file.

## Future Work: Multi-Queue System

The current single global queue does not scale well and makes resource management per engine difficult. A planned migration to a multi-queue system (motivated in part by adding a second GPU) would introduce:

- **Local pending queue** — Unprocessed local transcription tasks waiting to be picked up.
- **Local active queue** — One slot per GPU; ensures no GPU is double-booked.
- **Azure pending queue** — Unprocessed Azure transcription tasks.
- **Azure active queue** — Bounded by Azure's concurrent transcription limit.
- **Dead-letter queue** — Failed tasks, viewable via a dedicated API endpoint.
