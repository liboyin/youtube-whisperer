# YouTube Whisperer

## Overview

`youtube-whisperer` is a Python application that downloads YouTube videos and transcribes video files into SRT subtitle files, served via a RESTful API. The asset directory doubles as a human-browsable media library and the primary source of truth.

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
2. **Worker** — Consumes tasks from Redis, archives source media into the asset library, routes to the appropriate transcription engine for files without a corresponding transcript file, and writes `.srt` output.
3. **Redis** — Task queue shared between the API and worker.

## Data Flow

1. User submits a task via CLI or REST API, specifying the transcriber (`local` or `azure`) and language.
2. The API resolves file patterns and expands playlists, then enqueues the task in Redis.
3. A worker picks up the task.
4. For URLs, the worker first downloads and archives the video/audio, then attempts to fetch a pre-existing transcript.
5. If no transcript is available, the transcription engine processes the local media and an adaptor converts the output to an `.srt` file.

## Design Decisions

### Single-Worker Queue Model
The worker uses a non-atomic `LRANGE` + `LPOP` sequence by design. With a single GPU worker, atomicity is not a concern. This approach also provides automatic failure recovery: if the GPU fails mid-task (requiring a Docker container restart), the unfinished task remains at the head of the queue and is reprocessed automatically when the worker comes back online. Only failures that are expected to recover after a container restart are treated this way. Tasks that fail for known content-related reasons are currently discarded to avoid infinite retry loops. A dead-letter queue is the planned long-term solution.

### Dual Transcription Engines
The project started as a privacy-focused transcriber using local Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where local privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. Azure was chosen over other cloud providers as the most cost-effective option available in Sydney, Australia.

### Known-Bad Whisper Output Rejection
Some local Whisper runs occasionally emit known nonsense phrases instead of a real transcription. Those phrases are tracked in a centralized rejection list, and any local Whisper segment containing one of them causes the whole local run to be rejected without writing an SRT file.

### Filesystem as the Source of Truth
The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Worker as a Separate Process
The worker runs as an independent Docker service rather than background tasks within FastAPI, in preparation for scaling to multiple GPUs. Each GPU will run its own dedicated worker process.

### Azure Fire-and-Forget Dispatch
Azure transcription is currently dispatched asynchronously in a thread pool, and the Redis task is removed once submission succeeds rather than when the SRT file is written. This is a known gap: later Azure failures are only surfaced through logs and are not yet tracked in a dead-letter queue or task status store.

### Blocking I/O in Async Endpoints
`resolve_tasks()` makes blocking `yt-dlp` calls inside `async def` endpoints intentionally. The main goal is to keep the worker simple by enqueuing only concrete tasks. Running these YouTube interactions inside a single sequential request context also simulates single-user behaviour and avoids potential EULA violations from concurrent scraping.

### SRT as the Output Format
SRT was chosen to match an existing library of subtitle files. The conversion logic is isolated in the `adaptors/` layer, making it straightforward to support additional output formats (e.g. WebVTT, JSON) in the future.

### CLI as a Development Tool
The CLI runs the full pipeline in-process without Redis. It was designed primarily for development and testing within the devcontainer, not as a production interface.

## Future Work: Multi-Queue System

The current single global queue does not scale well and makes resource management per engine difficult. A migration to a multi-queue system is ready for execution (motivated by adding a second GPU) and would introduce:

- **YouTube queue + worker** — Dedicated to playlist expansion, video downloads, and transcript downloads. This would keep the transcription workers simple without forcing YouTube interactions to happen inside FastAPI requests.
- **Local pending queue** — Unprocessed local transcription tasks waiting to be picked up.
- **Local active queue** — One slot per GPU; ensures no GPU is double-booked.
- **Azure pending queue** — Unprocessed Azure transcription tasks.
- **Azure active queue** — Bounded by Azure's concurrent transcription limit.
- **Dead-letter queue** — Failed tasks, viewable via a dedicated API endpoint.
