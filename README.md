# YouTube Whisperer

## Overview

`youtube-whisperer` is a Python application that downloads YouTube videos and transcribes video files into SRT subtitle files, served via a RESTful API. The asset directory doubles as a human-browsable media library and the primary source of truth.

## Features

- **Download:** YouTube videos, playlists, and existing transcripts in a user-specified language.
- **Transcribe:** Generate SRT subtitle files from filesystem video/audio files.
- **Whisper transcriber:** `faster-whisper` on an NVIDIA GPU or CPU. Default model is `large-v3` (~9 GB RAM/VRAM). Runs synchronously.
- **Cloud transcriber:** Azure AI Speech Services, tracked synchronously per worker.
- **Task stream:** Redis-backed multi-stream scheduling with native Consumer Groups for dynamic assignment, failure catching, and message tracking.
- **Containerization:** Docker Compose with GPU and CPU support.

## Tech Stack

- Backend: Python + FastAPI
- Transcription: `faster-whisper` (whisper), `azure-cognitiveservices-speech` (cloud)
- YouTube: `yt-dlp`, `youtube-transcript-api`
- Video/Audio: ffmpeg
- Task Queue: Redis
- Containerization: Docker Compose

## Project Structure

```
youtube_whisperer/
├── __main__.py                 # CLI entry point: in-process pipeline, no Redis
├── config.py                   # Pydantic Settings loaded from environment / .env
├── utils.py                    # Shared enums, pooled Redis client, URL helper
├── queueing.py                 # Redis Streams: enqueue, snapshot, dead-letter
├── adaptors/
│   ├── lang_code_adaptor.py    # BCP-47 / ISO 639-1 LanguageCode type
│   └── srt_deduplicator.py     # SrtBlock serialization and SRT deduplication
├── downloaders/
│   ├── __init__.py             # download_video_and_transcript_with_default_title
│   ├── playlist_downloader.py  # Expand playlists/channels into video URLs
│   ├── transcript_downloader.py# Fetch an existing YouTube transcript as SRT
│   ├── video_downloader.py     # Download video/audio via yt-dlp
│   └── utils.py                # Video title lookup, Firefox cookie detection
├── transcriber/
│   ├── whisper_transcriber.py  # faster-whisper transcription
│   ├── azure_transcriber.py    # Azure Speech transcription
│   ├── model_parameters.py     # Whisper model and CPU/GPU device defaults
│   ├── rejection_policy.py     # Reject known-bad Whisper output
│   └── waveform_loader.py      # ffmpeg waveform / WAV loading
├── fastapi/
│   ├── app.py                  # REST API endpoints
│   └── models.py               # Pydantic request/response models
└── workers/
    ├── __main__.py             # Worker entry point: role dispatch
    ├── common.py               # BaseWorker and the stream-consume loop
    ├── youtube_worker.py       # Expand, download, enqueue follow-up tasks
    ├── whisper_worker.py       # Consume stream:whisper (with GPU health check)
    └── azure_worker.py         # Consume stream:azure

tests/                          # pytest suite mirroring the package layout
assets/                         # Media library and SRT output (source of truth)
Dockerfile                      # CUDA-based image build
docker-compose.yaml             # GPU services (extends the CPU compose file)
docker-compose.cpu.yaml         # CPU services: redis, app, and the three workers
```

## Architecture

Four main components cooperate:

1. **REST API** — Accepts tasks and assets. URL tasks are queued directly for the YouTube worker. Filesystem globs are still resolved in the API because they are cheap and do not require network I/O.
2. **YouTube worker** — Expands playlists, downloads video/audio, attempts transcript download, and enqueues follow-up filesystem media tasks for the requested transcriber only when an SRT is still missing.
3. **Transcription workers** — Whisper and Azure workers consume native Redis Streams utilizing Consumer Groups to track assignment identities.
4. **Redis** — Stores the streaming queues, tracks Consumer Pending Entries Lists (PEL), and archives dead letters.

## Data Flow

1. A user submits a task via CLI or REST API, specifying the transcriber (`whisper` or `azure`) and language.
2. FastAPI routes URL tasks to `stream:youtube`. Filesystem glob patterns are expanded immediately and concrete file paths are pushed to `stream:whisper` or `stream:azure`.
3. The YouTube worker expands playlist URLs, downloads media, and tries to fetch an existing transcript.
4. If a transcript is already present, the filesystem is considered complete and no follow-up transcription task is queued.
5. If a transcript is missing, the YouTube worker enqueues a concrete filesystem media task into the requested transcriber's stream.
6. A Whisper or Azure worker consumes the assignment natively via Consumer Groups, processes the media, and executes an `XACK` and `XDEL` against Redis after success or dead-lettering to preserve stream memory capacity.

## Queue Layout

- **`stream:youtube`** — Raw URL tasks waiting for playlist expansion, downloads, and transcript lookup.
- **`stream:whisper`** — Concrete filesystem media files waiting for Whisper transcription.
- **`stream:azure`** — Concrete filesystem media files waiting for Azure Speech processing.
- **`tasks:dead-letter`** — Failed tasks alongside origin stream strings and the execution stack trace causing unsuitability.

`GET /tasks` queries `XRANGE` and `XPENDING` natively over streams to produce snapshots differentiating Unclaimed assignments vs Actively Claimed tasks natively managed through Stream allocations. `GET /dead-letters` returns fully retired components from standard string lists.

## Design Decisions

### Redis Streams and Consumer Groups

The Whisper, Azure, and YouTube workers distribute work natively employing Redis Streams (`XADD` / `XREADGROUP`). Rather than implementing manual lists simulating "pending" vs explicit "active" bindings, system tasks are managed frictionlessly by a unified consumer group topology (`workers`). If an identity (e.g. `gpu-0`) fatally crashes midsentence, any subsequent pods launched inheriting identity `gpu-0` automatically extract their outstanding debts identically via their PEL (`0-0` inspection) before asking for new jobs.

### YouTube Work Runs Outside FastAPI

FastAPI only performs filesystem glob expansion. All network-facing YouTube work happens in the dedicated YouTube worker.

### Durable Azure Completion

Azure work uses Consumer Group flow natively. An Azure worker maintains the assignment mapped identically until `transcribe_audio_file()` finishes inside its local memory scope, acknowledging explicitly `XACK` so later Azure failures hit dead-letter logic securely.

### Dual Transcription Engines

The project started as a privacy-focused transcriber using Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where on-device privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. Azure was chosen over other cloud providers as the most cost-effective option available in Sydney, Australia.

### Known-Bad Whisper Output Rejection

Some Whisper runs occasionally emit known nonsense phrases instead of a real transcription. Those phrases are tracked in a centralized rejection list, and any Whisper segment containing one of them causes the whole run to be rejected without writing an SRT file.

### Filesystem as the Source of Truth

The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Worker as Separate Processes

Workers run as independent Docker services rather than background tasks within FastAPI. The default compose files now define `youtube_worker`, `whisper_worker`, and `azure_worker` services. Whisper and Azure workers derive their consumer name from `WORKER_SLOT_ID`, then the machine hostname, so scaled worker containers naturally govern exclusive message queues securely across parallel environments. The implementation is split across `workers/common.py` mapping stream architectures recursively onto standard abstract layers like `workers/youtube_worker.py`.

### SRT as the Output Format

SRT was chosen to match an existing library of subtitle files. SRT serialization and deduplication are isolated in `adaptors/srt_deduplicator.py`; each transcriber owns the small conversion from its native segment type to an `SrtBlock`. Supporting an additional output format (e.g. WebVTT, JSON) would mean adding a sibling serializer next to `save_segments_as_srt`.

### CLI as a Development Tool

The CLI runs the full pipeline in-process without Redis. It was designed primarily for development and testing within the devcontainer, not as a production interface.

## Configuration

Settings are read from environment variables (and `.env`) by `config.py`. All are optional except the Azure credentials, which are only required when using the Azure transcriber.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHISPER_ASSETS_DIR` | `<repo>/assets` | Media library and SRT output directory. |
| `WHISPER_MODELS_DIR` | `~/.whisper` | faster-whisper model cache. |
| `WHISPER_USE_CUDA` | unset (auto) | Force GPU (`1`) or CPU (`0`) for Whisper. |
| `WHISPER_MODEL` | `large-v3` | faster-whisper model name. |
| `AZURE_SPEECH_API_KEY` | unset | Azure Speech key (Azure transcriber only). |
| `AZURE_SERVICE_REGION` | unset | Azure Speech region (Azure transcriber only). |
| `WORKER_SLOT_ID` | unset | Stable consumer-slot id; falls back to the container hostname. |
| `WORKER_ROLE` | `whisper` | Default role when `python -m youtube_whisperer.workers` is run without one. |

`.env` (git-ignored) holds the Azure secrets and is loaded into every Compose service.

## Build & Run

### Dev Container (recommended)

Open the repository in VS Code and reopen in the Dev Container (`.devcontainer/`). The container builds from the `Dockerfile` via the `app` service and runs `postCreateCommand.sh`, which installs the pinned dependencies from `requirements.txt`, then installs this project with its dev extras (`pip install -e .[dev]`).

### Local install (without the Dev Container)

Requires Python ≥ 3.10 (the container uses 3.12), `ffmpeg`, and — for the API/worker flow — a reachable Redis server.

```
pip install -r requirements.txt   # pinned lock file
pip install -e .[dev]             # editable install + dev tooling
```

`requirements.txt` is a frozen lock file (regenerated by `postCreateCommand.sh` via `pip freeze`); `pyproject.toml` holds the abstract dependency set.

### Full stack with Docker Compose

```
docker compose up                              # GPU (NVIDIA runtime)
docker compose -f docker-compose.cpu.yaml up   # CPU only
```

This starts `redis`, `app` (FastAPI via uvicorn on port `8001`), `youtube_worker`, `whisper_worker`, and `azure_worker`. Interactive API docs are served at `http://localhost:8001/docs`. The REST API exposes `/tasks`, `/dead-letters`, and `/assets` (each with GET plus the relevant POST/DELETE).

### Running components directly

```
# REST API
uvicorn youtube_whisperer.fastapi.app:app --host 0.0.0.0 --port 8001

# Worker (one role per process)
python -m youtube_whisperer.workers {youtube|whisper|azure} [--slot ID] [--poll-interval-seconds N]

# CLI (in-process, no Redis) — accepts video/playlist URLs and/or local file paths
python -m youtube_whisperer <source>... -l <language> [-t whisper|azure] [-m transcribe|translate] [-o <overwrite-mode>]
```

The repository also ships `extract_subtitle_text.sh` (strip timestamps from an SRT) and `ls_mp4_without_srt.sh` (find videos lacking a sibling SRT).

## Testing

After any code change, all of the following MUST pass (see `pyproject.toml` for configuration):

```
pytest                  # runs in random order; enforces ≥80% branch coverage
mypy youtube_whisperer
ruff check .
```

`pytest` is configured to fail under 80% coverage and to print `--cov-report=term-missing`; use that report to confirm each file meets the ≥80% line/branch threshold required by `AGENTS.md`.

## Operational Notes

- Run exactly one `youtube_worker` unless you also introduce a YouTube active-slot policy.
- Run one `whisper_worker` per GPU.
- Run as many `azure_worker` processes as your Azure concurrency limit allows.
- If you want a stable slot name instead of the default container hostname, set `WORKER_SLOT_ID` to an integer.
