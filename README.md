# YouTube Whisperer

## Overview

`youtube-whisperer` is a Python application that downloads YouTube videos and transcribes video/audio files into SRT subtitle files, served via a RESTful API. The asset directory doubles as a human-browsable media library and the primary source of truth. It is designed as a personal, LAN-hosted service (see [Security / trust model](#security--trust-model)).

## Features

- **Download:** YouTube videos, playlists, and channels, plus existing transcripts in a user-specified language.
- **Transcribe:** Generate SRT subtitle files from filesystem video/audio files.
- **Whisper transcriber:** `faster-whisper` on an NVIDIA GPU or CPU. Default model is `large-v3` (~9 GB RAM/VRAM). Runs synchronously.
- **Cloud transcriber:** Azure AI Speech Services, tracked synchronously per worker.
- **Task queue:** Redis Streams with a shared consumer group for assignment, crash recovery, orphan recovery, and dead-lettering.
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
├── config.py                   # Pydantic Settings loaded from environment / .env
├── models.py                   # Pydantic domain + request/response models (Task, DeadLetter, ...)
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
│   ├── whisper_transcriber.py  # faster-whisper transcription (process-wide cached model)
│   ├── azure_transcriber.py    # Azure Speech transcription
│   ├── model_parameters.py     # Whisper model and CPU/GPU device defaults
│   ├── rejection_policy.py     # Reject known-bad Whisper output
│   └── waveform_loader.py      # ffmpeg waveform / WAV loading
├── api/
│   └── app.py                  # REST API endpoints (uses youtube_whisperer.models)
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
update_lock.sh                  # Regenerate requirements.txt from the environment (run by hand)
```

> Note: the web layer lives in `youtube_whisperer/api/` (renamed from `fastapi/`) so the package no longer shadows the third-party `fastapi` distribution, and the Pydantic models live in a neutral `youtube_whisperer/models.py` rather than inside the web layer, so the queue and worker layers do not import from the API layer.

## Architecture

Four components cooperate:

1. **REST API** (`api/app.py`) — Accepts tasks. URL tasks are queued directly for the YouTube worker. Filesystem glob patterns are resolved in the API itself because that is a cheap local operation with no network I/O.
2. **YouTube worker** — Expands playlists and channels, downloads video/audio, attempts a transcript download, and enqueues a follow-up filesystem transcription task (for the requested transcriber) only when an SRT is still missing.
3. **Transcription workers** — The Whisper and Azure workers consume their Redis streams via a shared consumer group and write SRT files.
4. **Redis** — Stores the streams, tracks each consumer's Pending Entries List (PEL), and holds the dead-letter list.

## Data Flow

1. A user submits one or more tasks via `POST /tasks`. Each task specifies a `source` (required — a YouTube URL or a filesystem glob), a transcriber (`whisper` or `azure`), and a language.
2. The API routes URL tasks to `stream:youtube`. Filesystem glob patterns are expanded immediately and the concrete file paths are pushed to `stream:whisper` or `stream:azure`.
3. The YouTube worker expands playlist/channel URLs, downloads media, and tries to fetch an existing transcript.
4. If a transcript is already present, the work is considered complete and no follow-up transcription task is queued.
5. If a transcript is missing, the YouTube worker enqueues a concrete filesystem task into the requested transcriber's stream.
6. A Whisper or Azure worker consumes the task via the consumer group, processes the media, and only then runs `XACK` + `XDEL` — so a failure dead-letters the task and a crash leaves it recoverable rather than silently dropped.

## Queue Layout

- **`stream:youtube`** — URL tasks awaiting playlist/channel expansion, download, and transcript lookup.
- **`stream:whisper`** — Concrete filesystem media files awaiting Whisper transcription.
- **`stream:azure`** — Concrete filesystem media files awaiting Azure Speech transcription.
- **`tasks:dead-letter`** — A list of failed tasks, each with its origin stream and error message.

`GET /tasks` reads each stream with `XRANGE` and its consumer group's pending entries with `XPENDING`, then reports unclaimed messages as *pending* and claimed (in-flight) messages as *active*. `GET /dead-letters` returns the dead-letter list.

## Design Decisions

### Redis Streams and a shared consumer group

The Whisper, Azure, and YouTube workers each read their stream through one shared consumer group (`workers`) using `XREADGROUP`. This gives three recovery properties without any hand-rolled "pending/active" bookkeeping:

- **Crash recovery:** before asking for new work, a worker re-reads its own PEL (`XREADGROUP ... 0-0`), so a task that was in flight when the worker crashed is reprocessed by the restarted worker under the same consumer name.
- **Orphan recovery:** a worker then runs `XAUTOCLAIM` to claim any message that has been idle longer than `WORKER_CLAIM_MIN_IDLE_SECONDS` (default 6 hours). This rescues tasks stranded in the PEL of a consumer name that will never come back (e.g. a container that was removed), which would otherwise show as "active" forever. The threshold is deliberately far above the longest plausible transcription so a task that is genuinely in flight on a live worker is never stolen.
- **Unique identities when scaled:** each worker's consumer name defaults to its container hostname, so `docker compose up --scale whisper_worker=3` yields three distinct consumers that do not fight over one PEL. Set `WORKER_SLOT_ID` only if you want a stable, explicit name instead.

### YouTube work runs outside the API

The API only performs local filesystem glob expansion. All network-facing YouTube work (expansion, download, transcript lookup) happens in the dedicated YouTube worker, so a slow or failing download never blocks an API request.

### Azure completion is synchronous per worker

`transcribe_audio_file()` blocks until Azure finishes, fails, or times out (`max(60s, 1.5 × audio duration)` — the floor keeps short clips from timing out during session startup). The worker acknowledges the message only after that call returns, so an Azure failure is dead-lettered rather than lost.

### The Whisper model is kept resident

`get_default_whisper_model()` builds the `WhisperModel` once per process and caches it (`functools.lru_cache`). On a dedicated GPU worker the multi-GB model is loaded once and reused across every queued task instead of being reloaded per file.

### Dual transcription engines

The project started as a privacy-focused transcriber using Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where on-device privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. Azure was chosen as the most cost-effective option in the Sydney, Australia region.

### Known-bad Whisper output rejection

Some Whisper runs occasionally emit a known nonsense phrase instead of a real transcription. Those phrases are listed in `REJECTED_SUBSTRINGS` in `transcriber/rejection_policy.py` (currently two recurring Chinese hallucination phrases). If any Whisper segment contains one, the whole run is rejected, no SRT is written, and the failure is raised so the worker dead-letters the task. Extend the list by editing that tuple.

### Language-code whitelist

Language codes are validated by `LanguageCode` in `adaptors/lang_code_adaptor.py` against a small whitelist: BCP-47 `en-us` and `zh-cn` (used by Azure) plus their ISO 639-1 forms `en` and `zh` (used by Whisper). A `source` or `source->target` request outside this set is rejected. To support another language, add its BCP-47 code to `BCP_LANG_CODES` (its ISO form is derived automatically).

### Filenames are truncated

Downloaded media and transcripts are named after the video title, with OS-reserved characters replaced and the full filename truncated to 220 characters (`video_downloader.py`, `transcript_downloader.py`) so long titles do not exceed filesystem name limits.

### Filesystem as the source of truth

The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Workers as separate processes

Workers run as independent Docker services rather than background tasks inside the API. The compose files define `youtube_worker`, `whisper_worker`, and `azure_worker`. Each worker's consumer name comes from `WORKER_SLOT_ID` if set, otherwise the container hostname (see [Redis Streams and a shared consumer group](#redis-streams-and-a-shared-consumer-group)). The shared loop lives in `workers/common.py`; each role subclass (`youtube_worker.py`, `whisper_worker.py`, `azure_worker.py`) only supplies its stream name and per-task work.

### SRT as the output format

SRT was chosen to match an existing library of subtitle files. SRT serialization and deduplication are isolated in `adaptors/srt_deduplicator.py`; each transcriber owns the small conversion from its native segment type to an `SrtBlock`. Supporting another output format (e.g. WebVTT, JSON) would mean adding a sibling serializer next to `save_segments_as_srt`.

## Security / trust model

The API is **unauthenticated by design** and assumes a trusted, LAN-only or single-user deployment. It exposes destructive and powerful operations — `DELETE /tasks`, `DELETE /assets`, and arbitrary filesystem-glob task sources — to any client that can reach it. Do **not** expose it directly to the public internet; put it behind a VPN, a reverse proxy with authentication, or a firewall.

## Configuration

Settings are read from environment variables (and `.env`) by `config.py`. All are optional except the Azure credentials, which are only required when using the Azure transcriber.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHISPER_ASSETS_DIR` | `<repo>/assets` | Media library and SRT output directory (inside the container). |
| `WHISPER_MODELS_DIR` | `~/.whisper` | faster-whisper model cache (inside the container). |
| `WHISPER_USE_CUDA` | unset (auto) | Force GPU (`1`) or CPU (`0`) for Whisper. |
| `WHISPER_MODEL` | `large-v3` | faster-whisper model name. |
| `AZURE_SPEECH_API_KEY` | unset | Azure Speech key (Azure transcriber only). |
| `AZURE_SERVICE_REGION` | unset | Azure Speech region (Azure transcriber only). |
| `REDIS_HOST` | `redis` | Redis hostname (the compose service name; set to `localhost` etc. when running outside compose). |
| `REDIS_PORT` | `6379` | Redis port. |
| `WORKER_SLOT_ID` | unset | Stable, explicit consumer name; falls back to the container hostname. |
| `WORKER_ROLE` | `whisper` | Default role when `python -m youtube_whisperer.workers` is run without one. |
| `WORKER_CLAIM_MIN_IDLE_SECONDS` | `21600` | Idle time before a worker claims a PEL entry stranded by another consumer. Keep it above the longest plausible transcription. |

`.env` (git-ignored) holds the Azure secrets and is loaded into every Compose service.

Compose also reads a few **interpolation** variables (host-side paths and build proxies) from your shell or `.env`, with working defaults so `docker compose up` runs on any machine:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ASSETS_DIR` | `./assets` | Host directory bind-mounted as the media library. |
| `WHISPER_MODELS_VOLUME` | `whisper_models` (named volume) | Host directory or volume for the Whisper model cache. |
| `FIREFOX_PROFILE_DIR` | `firefox_profile` (named volume) | Host Firefox profile for yt-dlp cookies; set it to download private/age-gated videos. |
| `APT_PROXY` | empty (none) | Optional apt caching proxy used during image build. |
| `PYPI_PROXY` | empty (none) | Optional PyPI proxy used during image build. |

## Build & Run

### Dev Container (recommended)

Open the repository in VS Code and reopen in the Dev Container (`.devcontainer/`). The container builds from the `Dockerfile` via the `app` service and runs `postCreateCommand.sh`, which installs the pinned dependencies from `requirements.txt` and then installs this project with its dev extras (`pip install -e .[dev]`). It no longer regenerates the lock file (see [Updating dependencies](#updating-dependencies)).

### Local install (without the Dev Container)

Requires Python ≥ 3.10 (the container uses 3.12), `ffmpeg`, and — for the API/worker flow — a reachable Redis server (set `REDIS_HOST`/`REDIS_PORT`).

```
pip install -r requirements.txt   # pinned lock file
pip install -e .[dev]             # editable install + dev tooling
```

`requirements.txt` is a frozen lock file; `pyproject.toml` holds the abstract dependency set.

### Full stack with Docker Compose

```
docker compose up                              # GPU (NVIDIA runtime)
docker compose -f docker-compose.cpu.yaml up   # CPU only
```

This starts `redis` (with a healthcheck the other services wait on), `app` (FastAPI via uvicorn on port `8001`), `youtube_worker`, `whisper_worker`, and `azure_worker`. Interactive API docs are served at `http://localhost:8001/docs`. The REST API exposes `/tasks` (GET/POST/DELETE), `/dead-letters` (GET/DELETE), and `/assets` (GET to list, DELETE to clean up redundant media). Scale a transcription worker with, e.g., `docker compose up --scale azure_worker=2`; the replicas get distinct consumer names automatically.

### Running components directly

```
# REST API
uvicorn youtube_whisperer.api.app:app --host 0.0.0.0 --port 8001

# Worker (one role per process)
python -m youtube_whisperer.workers {youtube|whisper|azure} [--slot ID] [--poll-interval-seconds N]
```

The repository also ships `extract_subtitle_text.sh` (strip timestamps from an SRT) and `ls_mp4_without_srt.sh` (find videos lacking a sibling SRT).

### Updating dependencies

`requirements.txt` is a lock file regenerated **intentionally**, not on every devcontainer create. After changing dependencies in `pyproject.toml` and reinstalling, run:

```
./update_lock.sh   # pip freeze (excluding this project) > requirements.txt
```

Then review and commit the updated lock file.

## Testing

After any code change, all of the following MUST pass (see `pyproject.toml` for configuration):

```
pytest                  # runs in random order; enforces ≥80% branch coverage
mypy youtube_whisperer
ruff check .
```

`pytest` is configured to fail under 80% coverage and to print `--cov-report=term-missing`; use that report to confirm each file meets the ≥80% line/branch threshold required by `AGENTS.md`.

## Operational Notes

- Run exactly one `youtube_worker`. Playlist/channel expansion and download are not idempotent across parallel expanders, so scaling the YouTube worker is not supported.
- Run one `whisper_worker` per GPU.
- Run as many `azure_worker` processes as your Azure concurrency limit allows; scaled replicas get unique consumer names automatically.
- Set `WORKER_SLOT_ID` only if you want a stable, explicit consumer name instead of the container hostname.
- Because the legacy `LanguageCode` repr-string format is no longer parsed, clear any old dead letters (`DELETE /dead-letters`) when upgrading from a much older build.

## Known Limitations

- **No authentication.** See [Security / trust model](#security--trust-model).
- **`DELETE /tasks` snapshots then deletes non-atomically.** `clear_task_queues` reads the streams and then deletes them in separate calls, so a task enqueued in the gap is deleted without appearing in the returned snapshot. This is benign at personal scale and left as-is.
- **Stranded-task recovery is time-bounded.** A task orphaned in a dead consumer's PEL is only reclaimed after `WORKER_CLAIM_MIN_IDLE_SECONDS` (default 6 hours), so it shows as "active" until then.
