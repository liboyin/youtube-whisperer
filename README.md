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
├── config.py                   # Pydantic Settings resolved from environment
├── domain.py                   # Resource-free transcriber enum and URL classifier
├── models.py                   # Pydantic domain + request/response models (Task, DeadLetter, ...)
├── utils.py                    # Redis pool factory and lazy compatible exports
├── runtime.py                  # Settings snapshot, configured paths, Redis ownership
├── queueing.py                 # Redis Streams: enqueue, snapshot, dead-letter
├── adaptors/
│   ├── lang_code_adaptor.py    # BCP-47 / ISO 639-1 LanguageCode type
│   └── srt_deduplicator.py     # Neutral SRT formatting, serialization and deduplication
├── downloaders/
│   ├── __init__.py             # download_video_and_transcript_with_default_title
│   ├── playlist_downloader.py  # Expand playlists/channels into video URLs
│   ├── transcript_downloader.py# Fetch an existing YouTube transcript as SRT
│   ├── video_downloader.py     # Download video/audio via yt-dlp
│   └── utils.py                # Shared yt-dlp defaults, title lookup, Firefox cookie detection
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
check-coverage.sh               # Run the suite and enforce the per-file coverage policy
```

> Note: the web layer lives in `youtube_whisperer/api/` (renamed from `fastapi/`) so the package no longer shadows the third-party `fastapi` distribution, and the Pydantic models live in a neutral `youtube_whisperer/models.py` rather than inside the web layer, so the queue and worker layers do not import from the API layer.

## Architecture

Four components cooperate:

1. **REST API** (`api/app.py`) — Accepts tasks. URL tasks are queued directly for the YouTube worker. Filesystem glob patterns are resolved in the API itself because that is a cheap local operation with no network I/O.
2. **YouTube worker** — Expands playlists and channels, then processes each expanded video independently: it downloads video/audio, attempts a transcript download, and enqueues a follow-up filesystem transcription task (for the requested transcriber) as soon as that video turns out to still be missing an SRT. A `none` transcriber requests download only, so no follow-up transcription task is ever enqueued.
3. **Transcription workers** — The Whisper and Azure workers consume their Redis streams via a shared consumer group and write SRT files.
4. **Redis** — Stores the streams, tracks each consumer's Pending Entries List (PEL), and holds the dead-letter list.

`domain.py` owns `TranscriberType` and `is_url`; models and queueing import domain values directly and construct no Settings, Redis pool, or Redis client when imported. Existing `utils.TranscriberType` and `utils.is_url` imports forward the same objects. Ordinary imports of `utils`, the API and workers also construct no settings or Redis resources. Explicit access to legacy `utils.REDIS_POOL`/`REDIS_CLIENT` creates a lazy compatibility runtime closed at process exit; legacy path exports resolve settings on each access. Existing public imports and positional transcription/download calls remain available.

The worker entrypoint loads no transcription or download engine when imported, when showing CLI help, or when rejecting an invalid role. Once a role is valid, it imports only that role's worker inside the runtime's cleanup scope: Whisper loads faster-whisper/CTranslate2, Azure loads Azure Speech, and YouTube loads yt-dlp/caption support. Direct worker-module classes and the older `workers.__main__` class imports remain available; the latter resolve lazily.

## Data Flow

1. A user submits one or more tasks via `POST /tasks`. Each task specifies a `source` (required — a YouTube URL or a filesystem glob), a transcriber (`whisper`, `azure`, or `none` to download a URL without transcribing it), a single source language (`en-us` by default).
2. The API routes URL tasks to `stream:youtube`. Filesystem glob patterns are expanded immediately; only files (including file symlinks, with no extension restriction) are pushed to `stream:whisper` or `stream:azure`, in glob order. Admitted paths are made absolute relative to the API working directory without resolving symlink aliases, so workers can run from a different working directory. Patterns matching no files are reported as failed.
3. The YouTube worker expands playlist/channel URLs into individual video URLs, then handles each video on its own: it downloads the media and tries to fetch an existing transcript.
4. If a transcript is already present (or the transcriber is `none`), that video is complete and no follow-up transcription task is queued.
5. Otherwise, if a transcript is missing, the YouTube worker immediately enqueues a concrete filesystem task for that video into the requested transcriber's stream, before moving to the next video.
6. If a video fails to download, look up captions, or enqueue its follow-up, that one video is dead-lettered under its own video URL and the remaining videos are still processed. See [Playlist videos succeed or fail independently](#playlist-videos-succeed-or-fail-independently).
7. A Whisper or Azure worker consumes the task via the consumer group, processes the media, and only then runs `XACK` + `XDEL` — so a failure dead-letters the task and a crash leaves it recoverable rather than silently dropped.

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
- **Orphan recovery:** a worker then runs `XAUTOCLAIM` to claim any message that has been idle longer than `WORKER_CLAIM_MIN_IDLE_SECONDS` (default 6 hours). Each generator follows the returned scan cursor across polling cycles, including empty pages, wraps when Redis returns `0-0`, and restarts its scan after recreating a missing group. It scans one claim page per cycle; an empty claim still permits a read for new work. This rescues tasks stranded in the PEL of a consumer name that will never come back (e.g. a container that was removed), which would otherwise show as "active" forever. The threshold is deliberately far above the longest plausible transcription so a task that is genuinely in flight on a live worker is never stolen.
- **Unique identities when scaled:** each worker's consumer name defaults to its container hostname, so `docker compose up --scale whisper_worker=3` yields three distinct consumers that do not fight over one PEL. Set `WORKER_SLOT_ID` only if you want a stable, explicit name instead.

### YouTube work runs outside the API

The API only performs local filesystem glob expansion. All network-facing YouTube work (expansion, download, transcript lookup) happens in the dedicated YouTube worker, so a slow or failing download never blocks an API request.

### Playlist videos succeed or fail independently

A playlist or channel task fans out into many videos, and one unavailable video should not cost the others their work. The YouTube worker therefore enqueues each video's follow-up transcription task as soon as that video is downloaded, instead of buffering them until the whole playlist finishes. A video that fails is dead-lettered under its own concrete video URL, carrying `stream:youtube` as its origin queue, and expansion continues with the next video. The parent playlist task is acknowledged once every expanded video has been attempted, so `GET /dead-letters` lists exactly the videos that need attention and each can be resubmitted on its own.

Two failures still belong to the parent task: a failure while expanding the playlist itself, and a failure to write the dead letter. Both propagate to the shared worker loop, which dead-letters (or, for an interrupt, leaves pending) the original task — follow-ups already enqueued for completed videos stay durable either way.

Reprocessing is safe. A recovered or resubmitted playlist re-downloads nothing that already exists under `OverwriteMode.NEVER`, and a video whose SRT has since been written reports its transcript as present, so no duplicate transcription task is queued.

### Azure completion is synchronous per worker

`transcribe_audio_file()` blocks until Azure finishes, fails, or times out (`max(60s, 1.5 × audio duration)` — the floor keeps short clips from timing out during session startup). The worker acknowledges the message only after that call returns, so an Azure failure is dead-lettered rather than lost. Azure carries the caller’s overwrite policy through preflight and final SRT saving: `ALWAYS` replaces output, `NEVER` preserves output even if it appears during recognition, and the default `PROMPT` asks for consent.

For non-WAV input, the Azure worker reuses an existing sidecar WAV or calls `save_as_wav_file` to convert mono PCM16 audio at 16 kHz. Conversion writes an exclusively created sibling stage with the caller destination suffix (default `.wav`) so ffmpeg retains its container inference. Only a successfully completed, reaped ffmpeg child permits publication; errors and interruptions kill any running child, drain/reap it and close owned pipes before stage cleanup. A failed conversion preserves previous good output and never calls Azure; retry regenerates the sidecar when none was published. Existing legacy WAVs remain reusable without retroactive validation or repair.

### The Whisper model is kept resident

`get_default_whisper_model()` builds its default `WhisperModel` lazily on the first uncached invocation and keeps it resident. Runtime helpers pass an immutable identity containing model name, cache directory, device, compute type and CPU threads to the same cache, so matching configurations reuse a model and differing snapshots cannot reuse the wrong one. `cache_clear()` releases every cached identity. No-argument default calls retain their initial model until cache cleanup; supplied settings control runtime model configuration independently. Each Whisper task still performs its live GPU health check when CUDA is enabled.

Whisper decoding passes the input path to ffmpeg and captures the complete mono PCM16 output in Python before converting it to a one-dimensional normalized float32 waveform. If decoding produces no samples, file transcription raises an error before loading the model or writing an SRT. The worker records that failure in the dead-letter list before acknowledging and deleting the task; if recording fails, the task remains pending. An existing SRT still satisfies the worker's `NEVER` policy without decoding the media.

### Dual transcription engines

The project started as a privacy-focused transcriber using Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where on-device privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. Azure was chosen as the most cost-effective option in the Sydney, Australia region.

### Transcription requests and upgrades

Both engines transcribe speech in the supplied source language. Tasks contain `source`, `transcriber`, and `language`; there is no operation selector or target language. Every supplied HTTP `mode` field, including `transcribe`, returns 422 before queue submission. Arrow-language forms such as `zh->en` and `en->en` also return 422.

For callers upgrading from translation support, omit `mode` and supply one source language. The Python `TranscriberMode` enum, `LanguageCode.target`, target conversion methods, and `MissingTargetLanguageCode` exception have been removed. Whisper waveform helpers now accept `(model, waveform, language)` and `(waveform, language)`; the file helper retains `(input_file_path, language, output_file_path=None, overwrite=...)` without a mode argument. Source-language conversion methods and other transcription APIs remain available.

Keep old producers from submitting work during the version switch, and confirm that no legacy queue or dead-letter payloads have appeared since the user reported those stores empty. No legacy-payload migration reader is provided; unexpected persisted payloads require manual repair under the existing queue policy. Existing media and SRT files remain untouched and eligible for the same completion/reuse checks, including SRTs created by past translations.

### Known-bad Whisper output rejection

Some Whisper runs occasionally emit a known nonsense phrase instead of a real transcription. Those phrases are listed in `REJECTED_SUBSTRINGS` in `transcriber/rejection_policy.py` (currently two recurring Chinese hallucination phrases). If any Whisper segment contains one, the whole run is rejected, no SRT is written, and the failure is raised so the worker dead-letters the task. Extend the list by editing that tuple.

### Language-code whitelist

Language codes are validated by `LanguageCode` in `adaptors/lang_code_adaptor.py` against a small whitelist: BCP-47 `en-us` and `zh-cn` (used by Azure) plus their ISO 639-1 forms `en` and `zh` (used by Whisper). A source-language request outside this set is rejected; target-language arrows are not accepted. To support another language, add its BCP-47 code to `BCP_LANG_CODES` (its ISO form is derived automatically).

### Filenames are truncated

Downloaded media and transcripts are named after the video title, with OS-reserved characters replaced and the full filename truncated to 220 characters (`video_downloader.py`, `transcript_downloader.py`) so long titles do not exceed filesystem name limits.

### Filesystem as the source of truth

The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Workers as separate processes

Workers run as independent Docker services rather than background tasks inside the API. The compose files define `youtube_worker`, `whisper_worker`, and `azure_worker`. Each worker's consumer name comes from `WORKER_SLOT_ID` if set, otherwise the container hostname (see [Redis Streams and a shared consumer group](#redis-streams-and-a-shared-consumer-group)). The shared loop lives in `workers/common.py`; each role subclass (`youtube_worker.py`, `whisper_worker.py`, `azure_worker.py`) only supplies its stream name and per-task work.

### SRT as the output format

SRT was chosen to match an existing library of subtitle files. Engine-neutral timestamp/text conversion, SRT serialization and deduplication live in `adaptors/srt_deduplicator.py`. The public Whisper and Azure converters retain native segment handling; Azure converts its offset/duration ticks to seconds without importing Whisper for formatting. Shared formatting rounds total milliseconds before decomposition, always includes hours, uses comma milliseconds, and strips outer text whitespace before splitting on newlines. Supporting another output format (e.g. WebVTT, JSON) would mean adding a sibling serializer next to `save_segments_as_srt`.

SRT saving, caption download, and in-place deduplication publish through `publish_srt_text`: complete text is written to an exclusively created sibling stage and closed before atomic publication. A failed write, close, or publication preserves the prior valid SRT; a process interrupted before publication cannot expose a partial final file. Whisper's lazy segments are fully consumed and checked before staging, and in-place deduplication reads its input before publication. Existing-output consent is obtained before expensive model/network work and reused without another prompt.

SRT and WAV publication share the same completion contract. `NEVER` and `RENAME` preserve existing output, including a competing file created during staging; `RENAME` retains its existing skip behavior rather than choosing a new filename. These policies use same-filesystem hard-link create-if-absent on Linux. A publication collision is skipped only when the destination is a file, including a symlink to a file; a late directory or dangling symlink propagates `FileExistsError` and removes the owned stage. Unsupported hard-link errors also propagate and remove the owned stage, without a fallback that could overwrite competing output. Approved replacement follows symlink targets and preserves existing mode bits; new files use ordinary 0666 permissions filtered by the inherited umask. Replacement creates a new inode, so hardlinked aliases retain old contents and ownership, ACLs, and extended attributes may change.

This protects completion markers from process interruption, without guaranteeing durability across power loss. An abrupt exit may leave a sibling `.srt-<random>.tmp` or `.wav-<random><destination-suffix>` stage; automatic scavenging is outside this behavior. Cleanup removes only successfully owned stages, preserving other writers' files on exclusive-creation collision. Existing legacy SRTs are still treated as complete under `NEVER`, without retroactive validation or repair.

### Build helpers come from a shared repository

The `apt` and `pip` steps of the image build live in [`docker-build-common`](https://github.com/liboyin/docker-build-common), not in this repo. They used to be local `docker_apt_install.sh` / `docker_pip_install.sh` scripts, copy-pasted across several projects and hand-synced, which drifted — fixes reached some repos and not others.

Compose supplies the helpers as a named build context (`build_common`) pinned to an immutable tag, and the Dockerfile bind-mounts that context for the length of each `RUN`. Bind-mounting rather than `COPY` keeps them build-time only: nothing is added to a layer and nothing ships in the image. `BUILD_COMMON_CONTEXT` overrides the pinned URL with a local clone, which both avoids the network and allows testing a helper change before it is tagged.

The consequence is that `docker build` on its own no longer works — it has no `build_common` context and BuildKit would look for an image by that name on Docker Hub. Build through Compose, or pass the context explicitly:

```
docker buildx build --build-context build_common=https://github.com/liboyin/docker-build-common.git#v1.0.0 .
```

## Security / trust model

The API is **unauthenticated by design** and assumes a trusted, LAN-only or single-user deployment. It exposes destructive and powerful operations — `DELETE /tasks`, `DELETE /assets`, and arbitrary filesystem-glob task sources — to any client that can reach it. Do **not** expose it directly to the public internet; put it behind a VPN, a reverse proxy with authentication, or a firewall.

## Configuration

Settings are read from exported environment variables by `config.py`; direct Python/API/worker launches do not load `.env` automatically. Compose injects `.env` into its application services. All settings are optional except the Azure credentials, which are only required when using the Azure transcriber.

API lifespan and worker execution each own one `Runtime` settings snapshot, configured asset/model paths, Redis client and pool. The CLI shares its snapshot with slot resolution and worker execution. Later environment changes do not alter claims, downloads, Azure credentials or model configuration for that runtime. `create_app(settings, client)` and worker keyword arguments accept supplied snapshots and concrete borrowed clients. Created clients and owned pools close on completion, startup failure and interruption; supplied clients/pools are borrowed unless pool ownership is explicitly transferred with `owns_pool=True`. Redis blocking reads retain no socket timeout, a five-second connection timeout and 60-second health checks.

Standalone download/model-parameter/CUDA/Azure helpers resolve missing defaults at invocation. Explicit paths and settings take precedence. A directly constructed worker resolves settings at construction and closes its own runtime when its queue loop exits; a supplied `runtime` remains caller-owned.

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
| `WORKER_CLAIM_MIN_IDLE_SECONDS` | `21600` | Idle time before a worker claims a PEL entry stranded by another consumer. Must be nonnegative; zero permits immediate claims. Keep it above the longest plausible transcription. |

`.env` (git-ignored) holds the Azure secrets and is loaded into every Compose service.

Compose also reads a few **interpolation** variables (host-side paths and build proxies) from your shell or `.env`, with working defaults so `docker compose up` runs on any machine:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ASSETS_DIR` | `./assets` | Host directory bind-mounted as the media library. |
| `WHISPER_MODELS_VOLUME` | `whisper_models` (named volume) | Host directory or volume for the Whisper model cache. |
| `FIREFOX_PROFILE_DIR` | `firefox_profile` (named volume) | Host Firefox profile for yt-dlp cookies; set it to download private/age-gated videos. |
| `APT_PROXY` | empty (none) | Optional apt caching proxy used during image build. |
| `PYPI_PROXY` | empty (none) | Optional PyPI proxy used during image build. |
| `BUILD_COMMON_CONTEXT` | pinned Git URL (`docker-build-common.git#v1.0.0`) | Source of the shared build helpers; point it at a local clone to build offline. |

## Build & Run

### Dev Container (recommended)

Open the repository in VS Code and reopen in the Dev Container (`.devcontainer/`). The container builds from the `Dockerfile` via the `app` service and runs `postCreateCommand.sh`, which installs the pinned dependencies from `requirements.txt` and then installs this project with its dev extras (`pip install -e .[dev]`). It also regenerates the lock file on every create (see [Updating dependencies](#updating-dependencies)).

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

The image build pulls its `apt`/`pip` helper scripts from the shared [`docker-build-common`](https://github.com/liboyin/docker-build-common) repository, so the first build needs to reach GitHub unless `BUILD_COMMON_CONTEXT` points at a local clone (see [Build helpers come from a shared repository](#build-helpers-come-from-a-shared-repository)).

This starts `redis` (with a healthcheck the other services wait on), `app` (FastAPI via uvicorn on port `8001`), `youtube_worker`, `whisper_worker`, and `azure_worker`. Interactive API docs are served at `http://localhost:8001/docs`. The REST API exposes `/tasks` (GET/POST/DELETE), `/dead-letters` (GET/DELETE), and `/assets` (GET to list, DELETE to clean up redundant media). Scale a transcription worker with, e.g., `docker compose up --scale azure_worker=2`; the replicas get distinct consumer names automatically.

### Running components directly

```
# REST API
uvicorn youtube_whisperer.api.app:app --host 0.0.0.0 --port 8001

# Worker (one role per process)
python -m youtube_whisperer.workers {youtube|whisper|azure} [--slot ID] [--poll-interval-seconds N]
```

Polling intervals must be positive integer seconds (default `5`) so each empty blocking read returns and orphan recovery can run again. The CLI and Python queue/poll entry points reject zero or negative polling; settings and direct polling reject negative claim-idle seconds before Redis commands.

The repository also ships `extract_subtitle_text.sh` (strip timestamps from an SRT) and `ls_mp4_without_srt.sh` (find videos lacking a sibling SRT).

### Updating dependencies

`requirements.txt` is a lock file. `.devcontainer/postCreateCommand.sh` regenerates it from the installed environment on every container create:

```
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
```

After changing dependencies in `pyproject.toml` and reinstalling, review and commit the regenerated lock file. Because the regeneration is a side effect of creating the container rather than a deliberate step, the lock file can also change on a plain rebuild; making it intentional is tracked in [TODO.md](TODO.md).

## Testing

For non-trivial code, test, or configuration changes, all of the following MUST pass before commit. [AGENTS.md](AGENTS.md#validation-and-review) owns baseline selection and documentation/cosmetic exceptions:

```
./check-coverage.sh     # runs the suite, then enforces the per-file coverage policy
mypy youtube_whisperer
ruff check .
```

`check-coverage.sh` runs `pytest` and then fails if any measured file, or the project total, falls below 80% statement or branch coverage. It owns the coverage policy that `AGENTS.md` requires, because pytest's own `--cov-fail-under` guards only the project total. Set `COVERAGE_THRESHOLD` to use a different threshold; extra arguments are forwarded to pytest.

`pyproject.toml` holds the pytest and coverage configuration. Tests run in random order via `pytest-randomly`, and the run prints its seed; reproduce an ordering failure with `--randomly-seed=<seed>`. Run `pytest` directly for focused work, but note that a subset run reports a coverage failure even when every selected test passes; pass `--no-cov` to silence it.

[The test bootstrap](tests/conftest.py) installs synthetic configuration before collecting application tests, including temporary home, asset, and model paths, an inert Redis endpoint, and no Azure credentials. It restores the process environment and removes its temporary directory when pytest exits. Start pytest in a fresh Python process; importing application settings before an embedded `pytest.main()` call, or repeating that call in the same process, is rejected because cached application modules would retain an earlier settings snapshot.

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
