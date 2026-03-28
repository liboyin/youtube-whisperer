# YouTube Whisperer

## Overview

`youtube-whisperer` is a Python application that downloads YouTube videos and transcribes video files into SRT subtitle files, served via a RESTful API. The asset directory doubles as a human-browsable media library and the primary source of truth.

## Features

- **Download:** YouTube videos, playlists, and existing transcripts in a user-specified language.
- **Transcribe:** Generate SRT subtitle files from filesystem video/audio files.
- **Whisper transcriber:** `faster-whisper` on an NVIDIA GPU or CPU. Default model is `large-v3` (~9 GB RAM/VRAM). Runs synchronously.
- **Cloud transcriber:** Azure AI Speech Services, tracked synchronously per worker slot so Redis state matches final SRT output.
- **Task queue:** Redis-backed multi-queue scheduling with pending, active-slot, and dead-letter queues.
- **Containerization:** Docker Compose with GPU and CPU support.

## Tech Stack

- Backend: Python + FastAPI
- Transcription: `faster-whisper` (whisper), `azure-cognitiveservices-speech` (cloud)
- YouTube: `yt-dlp`, `youtube-transcript-api`
- Video/Audio: ffmpeg
- Task Queue: Redis
- Containerization: Docker Compose

## Architecture

Four main components cooperate:

1. **REST API** — Accepts tasks and assets. URL tasks are queued directly for the YouTube worker. Filesystem globs are still resolved in the API because they are cheap and do not require network I/O.
2. **YouTube worker** — Expands playlists, downloads video/audio, attempts transcript download, and enqueues follow-up filesystem media tasks for the requested transcriber only when an SRT is still missing.
3. **Transcription workers** — Whisper and Azure workers each consume their own pending queue and claim one active slot queue per worker process.
4. **Redis** — Stores the YouTube queue, transcriber pending queues, active slot queues, and the dead-letter queue.

## Data Flow

1. A user submits a task via CLI or REST API, specifying the transcriber (`whisper` or `azure`) and language.
2. FastAPI routes URL tasks to `tasks:youtube`. Filesystem glob patterns are expanded immediately and concrete file paths are pushed to `tasks:whisper:pending` or `tasks:azure:pending`.
3. The YouTube worker expands playlist URLs, downloads media, and tries to fetch an existing transcript.
4. If a transcript is already present, the filesystem is considered complete and no follow-up transcription task is queued.
5. If a transcript is missing, the YouTube worker enqueues a concrete filesystem media task into the requested transcriber's pending queue.
6. A Whisper or Azure worker atomically claims work into its own active slot queue, processes the media, and removes the task from Redis only after success or dead-lettering.

## Queue Layout

- **`tasks:youtube`** — Raw URL tasks waiting for playlist expansion, downloads, and transcript lookup.
- **`tasks:whisper:pending`** — Concrete filesystem media files waiting for Whisper.
- **`tasks:whisper:active:<slot>`** — One active task per Whisper worker slot, typically one slot per GPU.
- **`tasks:azure:pending`** — Concrete filesystem media files waiting for Azure Speech.
- **`tasks:azure:active:<slot>`** — One active task per Azure worker slot. Run as many Azure workers as your concurrency budget allows.
- **`tasks:dead-letter`** — Failed tasks plus the queue that failed and the error message.

`GET /tasks` returns a snapshot of the YouTube, pending, and active queues. `GET /dead-letters` returns failed tasks.

## Design Decisions

### Slot-Based Active Queues

The Whisper and Azure active queues are implemented as slot-specific Redis lists such as `tasks:whisper:active:gpu-0`. This was the simplest way to satisfy "one slot per GPU" while keeping restart recovery: when a worker restarts, it first checks its own active queue and resumes the task already assigned to that slot before claiming new work.

### YouTube Work Runs Outside FastAPI

FastAPI only performs filesystem glob expansion. All network-facing YouTube work happens in the dedicated YouTube worker.

### Durable Azure Completion

Azure work no longer uses fire-and-forget dispatch from the queue consumer. An Azure worker now keeps the task in its active slot until `transcribe_audio_file()` finishes, so later Azure failures are dead-lettered instead of disappearing into logs.

### Dual Transcription Engines

The project started as a privacy-focused transcriber using Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where on-device privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. Azure was chosen over other cloud providers as the most cost-effective option available in Sydney, Australia.

### Known-Bad Whisper Output Rejection

Some Whisper runs occasionally emit known nonsense phrases instead of a real transcription. Those phrases are tracked in a centralized rejection list, and any Whisper segment containing one of them causes the whole run to be rejected without writing an SRT file.

### Filesystem as the Source of Truth

The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Worker as Separate Processes

Workers run as independent Docker services rather than background tasks within FastAPI. The default compose files now define `youtube_worker`, `whisper_worker`, and `azure_worker` services. Whisper and Azure workers derive their slot from `WORKER_SLOT`, then `HOSTNAME`, so scaled worker containers naturally get distinct active-slot queues. The implementation is split across `workers/common.py`, `workers/youtube_worker.py`, `workers/whisper_worker.py`, `workers/azure_worker.py`, and `workers/__main__.py`, which serves as the package entrypoint for `python -m youtube_whisperer.workers`.

### SRT as the Output Format

SRT was chosen to match an existing library of subtitle files. The conversion logic is isolated in the `adaptors/` layer, making it straightforward to support additional output formats (e.g. WebVTT, JSON) in the future.

### CLI as a Development Tool

The CLI runs the full pipeline in-process without Redis. It was designed primarily for development and testing within the devcontainer, not as a production interface.

## Operational Notes

- Run exactly one `youtube_worker` unless you also introduce a YouTube active-slot policy.
- Run one `whisper_worker` per GPU.
- Run as many `azure_worker` processes as your Azure concurrency limit allows.
- If you want a stable slot name instead of the default container hostname, set `WORKER_SLOT`.
