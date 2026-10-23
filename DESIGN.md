# System Design and Decisions

This document owns the current system design, product contracts, accepted user decisions and their rationale. [README](README.md) covers setup and operation; [TODO](TODO.md) owns outstanding work and unresolved choices; [AGENTS](AGENTS.md) and the repository skills own working procedures.

Decisions are grouped by topic and retain their D identifiers for backlog references. Implemented decisions remain constraints, not open tasks. Explicitly marked future decisions and historical premises do not describe current runtime behavior; superseded rules defer to their named successors. Do not recycle decision IDs or silently reinterpret accepted trade-offs. Record supersession and update affected backlog dependencies when a decision changes. Accepted limitations require no implementation unless their revisit condition is met or the user changes the decision; they do not waive AGENTS' safety requirements.

- [Product scope and trust](#product-scope-and-trust)
- [Architecture and resource ownership](#architecture-and-resource-ownership)
- [Task submission, queues and recovery](#task-submission-queues-and-recovery)
- [Media and subtitle behavior](#media-and-subtitle-behavior)
- [Deployment and configuration](#deployment-and-configuration)
- [Engineering governance](#engineering-governance)

## Product scope and trust

### Filesystem as the source of truth

The asset directory is intentionally a human-browsable media library rather than a cache. For YouTube sources, the video is archived locally even if a matching transcript already exists. Completed work is inferred from files on disk rather than from a separate metadata store.

### Security / trust model

The API is **unauthenticated by design** and assumes a trusted, LAN-only or single-user deployment. It exposes destructive and powerful operations — `DELETE /tasks`, `DELETE /assets`, and arbitrary filesystem-glob task sources — to any client that can reach it. Do **not** expose it directly to the public internet; put it behind a VPN, a reverse proxy with authentication, or a firewall.

### Transcription requests and upgrades

Both engines transcribe speech in the supplied source language. Tasks contain `source`, `transcriber`, and `language`; there is no operation selector or target language. Every supplied HTTP `mode` field, including `transcribe`, returns 422 before queue submission. Arrow-language forms such as `zh->en` and `en->en` also return 422.

For callers upgrading from translation support, omit `mode` and supply one source language. The Python `TranscriberMode` enum, `LanguageCode.target`, target conversion methods, and `MissingTargetLanguageCode` exception have been removed. Whisper waveform helpers now accept `(model, waveform, language)` and `(waveform, language)`; the file helper retains `(input_file_path, language, output_file_path=None, overwrite=...)` without a mode argument. Source-language conversion methods and other transcription APIs remain available.

When upgrading from a translation-capable version, stop old producers and inspect queue/dead-letter compatibility before switching. D25 records a historical empty-store report, not an assurance about a later deployment. No legacy-payload migration reader is provided; unexpected persisted payloads require manual repair under the existing queue policy. Existing media and SRT files remain untouched and eligible for the same completion/reuse checks, including SRTs created by past translations.

### Language-code whitelist

Language codes are validated by `LanguageCode` in `adaptors/lang_code_adaptor.py` against a small whitelist: BCP-47 `en-us` and `zh-cn` (used by Azure) plus their ISO 639-1 forms `en` and `zh` (used by Whisper). BCP-47 forms work with both engines; ISO forms work with Whisper, while Azure requires BCP-47 at execution. A source-language request outside this set is rejected; target-language arrows are not accepted. To support another language, add its BCP-47 code to `BCP_LANG_CODES` (its ISO form is derived automatically).

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d5"></a>D5 | The API is unauthenticated and LAN-only by design. This document owns the trust model. | legacy finding 25 |
| <a id="d23"></a>D23 | Remove all project translation features instead of implementing translation-caption routing. This changes the product contract; NB32 implemented the removal. | B4; NB32; related README and backlog references |
| <a id="d24"></a>D24 | Remove the mode enum, target-language APIs, and mode parameters outright; the user accepts the resulting Python API break. Reject every supplied HTTP `mode` field with 422, including `transcribe`, so obsolete clients cannot silently request a different operation. This supersedes D18 only for the APIs and parameters removed by NB32; unrelated transcription APIs retain their compatibility contract. | NB32; Task and LanguageCode; Whisper helpers |
| <a id="d25"></a>D25 | **Historical rollout premise (2026-09-29), not current queue state:** the user reported no queued tasks or dead letters. No legacy-payload migration or compatibility reader was planned. This is user-provided state, not a live Redis inspection; deployment must keep old producers from creating incompatible payloads during the switch. | NB32 rollout; D12 remains in force |
| <a id="d26"></a>D26 | Preserve existing media/SRT files and existing SRT reuse behavior, including files that may contain past translations. Do not add automatic classification, cleanup, or mandatory manual review of those files. | NB32 rollout; filesystem completion contract |

## Architecture and resource ownership

Four components cooperate:

1. **REST API** (`api/app.py`) — Accepts tasks. URL tasks are queued directly for the YouTube worker. Filesystem glob patterns are resolved in the API process itself because that is a cheap local operation with no network I/O. `task_preparation.py` owns request preparation (URL classification, rejection of local `none` sources, filesystem resolution and successful/failed bookkeeping) and loads neither FastAPI nor Redis; the endpoint submits the prepared routing lists through `queueing` and serializes the HTTP response.
2. **YouTube worker** — Expands playlists and channels, then processes each expanded video independently: it downloads video/audio, attempts a transcript download, and enqueues a follow-up filesystem transcription task (for the requested transcriber) as soon as that video turns out to still be missing an SRT. A `none` transcriber requests download only, so no follow-up transcription task is ever enqueued.
3. **Transcription workers** — The Whisper and Azure workers consume their Redis streams via a shared consumer group and write SRT files.
4. **Redis** — Stores the streams, tracks each consumer's Pending Entries List (PEL), and holds the dead-letter list.

`domain.py` owns `TranscriberType` and `is_url`; models and queueing import domain values directly and construct no Settings, Redis pool, or Redis client when imported. Existing `utils.TranscriberType` and `utils.is_url` imports forward the same objects. Ordinary imports of `utils`, the API and workers also construct no settings or Redis resources; `task_preparation` imports only domain values and models. Explicit access to legacy `utils.REDIS_POOL`/`REDIS_CLIENT` creates a lazy compatibility runtime closed at process exit; legacy path exports resolve settings on each access. Existing public imports and positional transcription/download calls remain available.

The worker entrypoint loads no transcription or download engine when imported, when showing CLI help, or when rejecting an invalid role. Once a role is valid, it imports only that role's worker inside the runtime's cleanup scope: Whisper loads faster-whisper/CTranslate2, Azure loads Azure Speech, and YouTube loads yt-dlp/caption support. Direct worker-module classes and the older `workers.__main__` class imports remain available; the latter resolve lazily.

### Workers as separate processes

Workers run as independent Docker services rather than background tasks inside the API. The compose files define `youtube_worker`, `whisper_worker`, and `azure_worker`. The CLI resolves each worker's consumer name from `--slot` when supplied, otherwise `<role>-<WORKER_SLOT_ID>` when configured, and otherwise the hostname (see [Redis Streams and a shared consumer group](#redis-streams-and-a-shared-consumer-group)). The shared `BaseWorker` in `workers/common.py` owns stream and consumer identity, compatible accessors, runtime resources, and the recovery/acknowledgement loop. Role subclasses (`youtube_worker.py`, `whisper_worker.py`, `azure_worker.py`) supply identity during construction and retain their per-task work. The poller shares payload validation and missing-group recovery while keeping own-pending, orphan-claim, and new-work reads explicit.

### Settings and runtime ownership

API lifespan and worker execution each own one `Runtime` settings snapshot, configured asset/model paths, Redis client and pool. The CLI shares its snapshot with slot resolution and worker execution. Later environment changes do not alter claims, downloads, Azure credentials or model configuration for that runtime. `create_app(settings, client)` and worker keyword arguments accept supplied snapshots and concrete borrowed clients. Created clients and owned pools close on completion, startup failure and interruption; supplied clients/pools are borrowed unless pool ownership is explicitly transferred with `owns_pool=True`. Redis blocking reads retain no socket timeout, a five-second connection timeout and 60-second health checks.

Standalone download/model-parameter/CUDA/Azure helpers resolve missing defaults at invocation. Explicit paths and settings take precedence. A directly constructed worker resolves settings at construction and closes its own runtime when its queue loop exits; a supplied `runtime` remains caller-owned.

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d18"></a>D18 | Preserve existing public Python APIs while simplifying internals. Low internal call counts do not justify removing `TranscriptDownloader`, convenience wrappers, or language helpers used by external scripts. Use compatible forwarding where internal ownership moves. | Simplification work; NB25–NB27 |
| <a id="d19"></a>D19 | Create settings and long-lived resources explicitly at API/worker startup, and load only the selected worker engine. Domain imports should not initialize unrelated Redis resources. CLI and HTTP behavior remain stable. | NB25, NB26 |
| <a id="d20"></a>D20 | Each API/worker process uses one settings snapshot; standalone Python helpers resolve defaults when called. This replaces the mixed import-time/per-task lookup policy, while preserving environment-only direct-run configuration (D14), explicit overrides, and the resident Whisper model. | NB25 |
| <a id="d21"></a>D21 | Pass stream and consumer identity into the shared base worker as constructor data, eliminating repeated getter-only overrides. Retain the existing worker subclasses and authoritative recovery/acknowledgement loop; preserve compatible public accessors where needed under D18. | NB27 |
| <a id="d27"></a>D27 | Accept without change the NB25 review's non-blocking race on concurrent first access to legacy `utils.REDIS_CLIENT`/`REDIS_POOL`. At acceptance, the user reported a clean deployment with no Redis entries and declined further work on this compatibility path. Empty Redis does not remove the Python first-access race; revisit if concurrent legacy callers require one shared client/pool pair. | NB25 compatibility exports; review at e8b34dd |
| <a id="d42"></a>D42 | The user decided (2026-10-11) that the `DELETE /assets` helpers `map_path_to_suffixes` and `redundant_media_paths` are endpoint internals that D18 does not require preserving. N1 replaced them in place: `group_files_by_stem` groups actual files and `redundant_media_paths` selects actual paths, instead of keeping their lowercased-suffix signatures. The user also chose a new `youtube_whisperer/task_preparation.py` module for `POST /tasks` preparation, which NB29 implemented; `api.app.resolve_filesystem_tasks` forwards the same object. Endpoint coroutines keep their names and parameters. | N1, NB29 (implemented) |

### Project Structure

```
youtube_whisperer/
├── config.py                   # Pydantic Settings resolved from environment
├── domain.py                   # Resource-free transcriber enum and URL classifier
├── models.py                   # Pydantic domain + request/response models (Task, DeadLetter, ...)
├── utils.py                    # Redis pool factory and lazy compatible exports
├── runtime.py                  # Settings snapshot, configured paths, Redis ownership
├── queueing.py                 # Redis Streams: enqueue, snapshot, dead-letter
├── task_preparation.py         # POST /tasks preparation: classify, resolve globs, report failures
├── overwrite.py                # Supported overwrite policies and the existing-output preflight (D48)
├── adaptors/
│   ├── lang_code_adaptor.py    # BCP-47 / ISO 639-1 LanguageCode type
│   └── srt_deduplicator.py     # Neutral SRT formatting, serialization and deduplication
├── downloaders/
│   ├── __init__.py             # download_video_and_transcript_with_default_title
│   ├── playlist_downloader.py  # Expand playlists/channels into video URLs
│   ├── transcript_downloader.py# Fetch an existing YouTube transcript as SRT
│   ├── video_downloader.py     # Download video/audio via yt-dlp
│   └── utils.py                # Shared yt-dlp defaults, title/ID lookup, default filenames, Firefox cookie detection
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

## Task submission, queues and recovery

### Data Flow

1. A user submits one or more tasks via `POST /tasks`. Each task specifies a `source` (required — a YouTube URL or a filesystem glob), a transcriber (`whisper`, `azure`, or `none` to download a URL without transcribing it), a single source language (`en-us` by default).
2. The API routes URL tasks to `stream:youtube`. Filesystem glob patterns are expanded immediately; only files (including file symlinks, with no extension restriction) are pushed to `stream:whisper` or `stream:azure`, in glob order. Admitted paths are made absolute relative to the API working directory without resolving symlink aliases, so workers can run from a different working directory. Patterns matching no files are reported as failed.
3. The YouTube worker expands playlist/channel URLs into individual video URLs, then handles each video on its own: it downloads the media and tries to fetch an existing transcript.
4. If a transcript is already present (or the transcriber is `none`), that video is complete and no follow-up transcription task is queued.
5. Otherwise, if a transcript is missing, the YouTube worker immediately enqueues a concrete filesystem task for that video into the requested transcriber's stream, before moving to the next video.
6. If a video fails to download, fails a caption step for any reason other than a caption-service error, or its follow-up cannot be enqueued, that one video is dead-lettered under its own video URL and the remaining videos are still processed. A caption-service error after a successful download is logged and treated as missing captions under [D16](#d16). See [Playlist videos succeed or fail independently](#playlist-videos-succeed-or-fail-independently).
7. A Whisper or Azure worker consumes the task via the consumer group, processes the media, and only then runs `XACK` + `XDEL` — so a failure dead-letters the task and a crash leaves it recoverable rather than silently dropped.

### Queue Layout

- **`stream:youtube`** — URL tasks awaiting playlist/channel expansion, download, and transcript lookup.
- **`stream:whisper`** — Concrete filesystem media files awaiting Whisper transcription.
- **`stream:azure`** — Concrete filesystem media files awaiting Azure Speech transcription.
- **`tasks:dead-letter`** — A list of failed tasks, each with its origin stream and error message.

`GET /tasks` reads each stream with `XRANGE` and its consumer group's pending entries with `XPENDING`, then reports transcription messages as *pending* when unclaimed and *active* when claimed (in-flight); the `youtube` field combines both states. `GET /dead-letters` returns the dead-letter list.

### HTTP contracts

The [API](youtube_whisperer/api/app.py) uses the [task and response models](youtube_whisperer/models.py). Interactive schemas are available at `/docs` on the running service.

| Endpoint | Current behavior |
|---|---|
| `POST /tasks` | Accepts a list of tasks; returns 201 with `successful` and `failed` lists, even when all valid patterns are non-actionable. A source is required, trimmed and nonblank; defaults are transcriber `whisper` and language `en-us`. URL tasks are submitted before resolved filesystem tasks, while response lists retain input/expansion order. Patterns matching no files and local sources with `none` are reported as failed. Submission is best-effort under D11. |
| `GET /tasks` | Returns `youtube`, `whisper_pending`, `whisper_active`, `azure_pending` and `azure_active`; the YouTube field combines unclaimed and in-flight tasks. This is a queue snapshot, not a completion history. |
| `DELETE /tasks` | Returns the snapshot read before deleting all routing streams; concurrent arrivals can be lost under D6. A concurrent submission that recreates a deleted stream is still delivered ([D43](#d43)). It does not cancel work already executing in a worker. |
| `GET /dead-letters` | Returns failed tasks in insertion order, each with `task`, origin `queue` and `error`. |
| `DELETE /dead-letters` | Returns the list read before deletion; concurrent appends can be lost under D9. |
| `GET /assets` | Returns sorted paths of all entries recursively under the configured asset directory, including directories. |
| `DELETE /assets` | Removes the actual MKV/WAV/MP3 files sharing a path without suffix with an MP4 + SRT pair, matching suffixes case-insensitively (every case variant, such as `video.wav` and `video.WAV`, is removed); stems themselves are compared exactly. Returns the sorted removed paths as spelled on disk; MP4/SRT files are retained. A selected file already gone at deletion is skipped and not reported; other deletion errors return 500. |

Model validation errors return 422, including a `language` value that is not a string (number, `null`, list, object or boolean). Unexpected endpoint exceptions return a generic 500 response while the server logs the exception. Filesystem task sources are not restricted to the asset directory; this is part of the trusted deployment contract.

### Redis Streams and a shared consumer group

The Whisper, Azure, and YouTube workers each read their stream through one shared consumer group (`workers`) using `XREADGROUP`. The worker loop provides recovery and consumer identity as follows:

- **Crash recovery:** before asking for new work, a worker re-reads its own PEL (`XREADGROUP ... 0-0`), so a task that was in flight when the worker crashed is reprocessed by the restarted worker under the same consumer name.
- **Orphan recovery:** a worker then runs `XAUTOCLAIM` to claim any message that has been idle longer than `WORKER_CLAIM_MIN_IDLE_SECONDS` (default 6 hours). Each generator follows the returned scan cursor across polling cycles, including empty pages, wraps when Redis returns `0-0`, and restarts its scan after recreating a missing group. It scans one claim page per cycle; an empty claim still permits a read for new work. This rescues tasks stranded in the PEL of a consumer name that will never come back (e.g. a container that was removed), which would otherwise show as "active" forever. The threshold is intended to exceed expected transcription duration; it is an idle-time heuristic, not a guarantee that a live task cannot be reclaimed.
- **Group creation:** submitters and workers create a missing `workers` group from the start of the stream (ID `0`), and a worker recreates it the same way after `NOGROUP`. Workers acknowledge and delete every processed entry, so anything left in a stream is unprocessed and is delivered once the group exists again, including a task whose submission recreated a stream deleted by `DELETE /tasks` ([D43](#d43)). An existing group is never reset.
- **Unique identities when scaled:** each worker's consumer name defaults to its container hostname, so `docker compose up --scale azure_worker=3` yields three distinct consumers. If setting `WORKER_SLOT_ID` or `--slot`, assign a unique name to each concurrent consumer of the same stream; a shared value defeats this isolation.

### YouTube work runs outside the API

The API only performs local filesystem glob expansion. All network-facing YouTube work (expansion, download, transcript lookup) happens in the dedicated YouTube worker, so a slow or failing download never blocks an API request.

Caption listing and fetching share one `requests` session per video, closed when the lookup ends. Each caption HTTP request defaults to a 10-second connect and 30-second read timeout ([D38](#d38)), so a stalled caption response cannot hold the single YouTube worker indefinitely. The read timeout bounds silence between bytes, not total transfer time: a response that keeps trickling data remains unbounded. Video download and playlist expansion run through yt-dlp and are not covered by this timeout.

### API requests do not block the event loop

The API runs as one uvicorn process with a single event loop. Each endpoint remains an `async def` coroutine function ([D18](#d18)) and runs its blocking Redis, glob, directory-traversal and deletion work through one `starlette.concurrency.run_in_threadpool` call per request; FastAPI already runs the synchronous `get_redis_client`/`get_assets_dir` dependencies in the same threadpool. A stalled Redis call or a large traversal therefore holds one worker thread instead of the event loop, and independent requests keep completing. Exceptions from offloaded work still reach the sanitized 500 handler.

Limitation: the threadpool uses anyio's default capacity limiter (40 tokens, shared with FastAPI's synchronous dependencies), which bounds how many requests can be blocked at once; further requests wait for a token. Per-request timeouts and threadpool sizing are not configured, and the Redis client keeps no socket read timeout (see [Settings and runtime ownership](#settings-and-runtime-ownership)). Because requests can now overlap, concurrent `DELETE /assets` requests may select the same file; the one that finds it already gone skips it, as described under [HTTP contracts](#http-contracts). A `POST /tasks` that overlaps `DELETE /tasks` can recreate a stream without its consumer group; the group is then recreated from the stream start, so that task is still delivered ([D43](#d43)).

### Playlist videos succeed or fail independently

A playlist or channel task fans out into many videos, and one unavailable video should not cost the others their work. The YouTube worker therefore enqueues each video's follow-up transcription task as soon as that video is downloaded, instead of buffering them until the whole playlist finishes. A video that fails is dead-lettered under its own concrete video URL, carrying `stream:youtube` as its origin queue, and expansion continues with the next video. The parent playlist task is acknowledged once every expanded video has been attempted, so `GET /dead-letters` lists exactly the videos that need attention and each can be resubmitted on its own.

Two failures still belong to the parent task: a failure while expanding the playlist itself, and a failure to write the dead letter. Both propagate to the shared worker loop, which dead-letters (or, for an interrupt, leaves pending) the original task — follow-ups already enqueued for completed videos stay durable either way.

Existing-file checks limit repeated work. A recovered or resubmitted playlist re-downloads nothing that already exists under `OverwritePolicy.NEVER`, and a video whose SRT has since been written reports its transcript as present, so no follow-up is queued for that completed file. Recovery before the SRT exists can enqueue duplicate transcription work; this is not an exactly-once guarantee.

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d6"></a>D6 | `clear_task_queues` snapshots and then deletes non-atomically. Accepted without change and documented as a known limitation. | legacy finding 11 |
| <a id="d9"></a>D9 | Accept the read-then-delete race for dead letters as well as task queues. A concurrent append may be removed without appearing in the returned snapshot. | `DELETE /dead-letters`; extends D6's accepted limitation |
| <a id="d11"></a>D11 | Accept best-effort batch submission: a later enqueue failure may return 500 after earlier tasks were queued, and a client retry can duplicate them. | `POST /tasks` |
| <a id="d12"></a>D12 | Manual Redis repair is acceptable for malformed/older persisted payloads; automated quarantine or schema recovery is not requested. | Worker deserialization and queue administration |
| <a id="d13"></a>D13 | Support API and worker processes launched from different working directories by resolving filesystem task paths absolutely. | NB22 |
| <a id="d16"></a>D16 | After successful video download, caption-service errors allow download-only completion or the requested transcription fallback. NB24 implemented it. | NB24; supersedes fatal caption-service errors for this case |
| <a id="d17"></a>D17 | A playlist/channel video that fails does not stop the remaining videos. Each failed video is dead-lettered under its own concrete video URL so it can be retried alone, and the parent task is acknowledged once every expanded video has been attempted. The user chose continue-and-report over stopping at the first failure because one private or unavailable video should not cost a large playlist its work. | B3 (implemented); NB24 keeps it for non-caption-service failures |
| <a id="d38"></a>D38 | Bound each caption HTTP request with a fixed 10-second connect and 30-second read timeout. The value is a module constant, not a setting. The user chose a per-request timeout over a configurable value or a wall-clock watchdog, accepting that slow-drip responses remain unbounded. | NB19 (implemented) |
| <a id="d39"></a>D39 | Report a caption-service error absorbed under D16 as a WARNING log with URL and traceback, without a dead letter. The user chose this so `GET /dead-letters` keeps meaning "needs attention" and resubmission does not repeat completed work. | NB24 (implemented) |
| <a id="d43"></a>D43 | Create a missing consumer group from stream ID `0` instead of the default `$`. Concurrent `POST /tasks`/`DELETE /tasks` requests (possible since NB15) or a YouTube follow-up racing `DELETE /tasks` could recreate a stream without its group, and a group created at `$` silently skipped that task while `GET /tasks` listed it as pending forever. Every processed entry is acknowledged and deleted, so starting at `0` delivers only unprocessed work; a manually destroyed group with in-flight entries may redeliver them, consistent with the existing duplicate tolerance. A main-agent gap review (2026-10-11) offered this fix or documenting the outcome under D6; the user asked for the gap to be fixed. D6 still allows a task to be lost if its stream is deleted after the append. | NB35; `ensure_consumer_group` |

Under D16 and [D39](#d39), the caption step that follows a successful video download treats `youtube_transcript_api.YouTubeTranscriptApiException` and `requests.RequestException` (including D38 timeouts) as missing captions. It logs a WARNING with the URL and traceback, and returns no transcript. The worker then completes a `none` task or enqueues the requested Whisper/Azure follow-up, without writing a dead letter. Disabled or unavailable-language captions keep their existing missing-caption handling. Every other error still dead-letters that one video under D17. This covers a failed media download (no captions are attempted), an unsupported URL rejected by video-ID parsing, local SRT publication errors, and programming errors. It also covers malformed caption payloads that the library does not wrap, such as XML `ParseError` or `KeyError`. A non-JSON innertube response is the exception: the library's `.json()` call raises `requests.exceptions.JSONDecodeError`, which is a `RequestException`, so it is absorbed as missing captions.

## Media and subtitle behavior

### Azure completion is synchronous per worker

`transcribe_audio_file()` blocks until Azure finishes, fails, or times out (`max(60s, 1.5 × audio duration)` — the floor keeps short clips from timing out during session startup). Audio duration is inspected before the recognizer is created, and every start attempt is followed by a stop on success, timeout, Azure cancellation, startup failure or interruption; no SRT is written when recognition fails. The worker acknowledges the message only after that call returns, so an Azure failure is dead-lettered rather than lost. Azure carries the caller’s overwrite policy through preflight and final SRT saving: `ALWAYS` replaces output, and the default `NEVER` preserves output even if it appears during recognition ([D48](#d48)).

For non-WAV input, the Azure worker calls `save_as_wav_file` under `NEVER`, which keeps and reuses an existing sidecar WAV and otherwise converts mono PCM16 audio at 16 kHz; the source must exist in both cases ([D49](#d49)). Conversion runs inside a `StagedFile` whose stage file takes the caller's destination name (default suffix `.wav`) through its name option, and writes that exclusively created file, so ffmpeg infers the container from that suffix even when a symlinked destination's target has another one ([D49](#d49)). Only a successfully completed, reaped ffmpeg child permits publication; errors and interruptions kill any running child, drain/reap it and close owned pipes before stage cleanup. A failed conversion preserves previous good output and never calls Azure; retry regenerates the sidecar when none was published. Existing legacy WAVs remain reusable without retroactive validation or repair.

### The Whisper model is kept resident

`get_default_whisper_model()` builds its default `WhisperModel` lazily on the first uncached invocation and keeps it resident. Runtime helpers pass an immutable identity containing model name, cache directory, device, compute type and CPU threads to the same cache, so matching configurations reuse a model and differing snapshots cannot reuse the wrong one. `cache_clear()` releases every cached identity. No-argument default calls retain their initial model until cache cleanup; supplied settings control runtime model configuration independently. Each Whisper task still performs its live GPU health check when CUDA is enabled.

Whisper decoding passes the input path to ffmpeg and captures the complete mono PCM16 output in Python before converting it to a one-dimensional normalized float32 waveform. If decoding produces no samples, file transcription raises an error before loading the model or writing an SRT. The worker records that failure in the dead-letter list before acknowledging and deleting the task; if recording fails, the task remains pending. An existing SRT still satisfies the worker's `NEVER` policy without decoding the media.

### Dual transcription engines

The project started as a privacy-focused transcriber using Whisper. Azure Speech was added later for two reasons: (1) transcribing public content where on-device privacy guarantees are unnecessary, and (2) working around occasional Whisper failures on non-English audio. The recorded selection rationale was cost in the Sydney, Australia region; this is historical context, not a current pricing comparison.

### Known-bad Whisper output rejection

Some Whisper runs occasionally emit a known nonsense phrase instead of a real transcription. Those phrases are listed in `REJECTED_SUBSTRINGS` in `transcriber/rejection_policy.py` (currently two recurring Chinese hallucination phrases). If any Whisper segment contains one, the whole run is rejected, no SRT is written, and the failure is raised so the worker dead-letters the task. Extend the list by editing that tuple.

### Filenames carry the title and video ID

Downloaded media and transcripts are named `Title [videoID].ext`, such as `Mr. Smith Goes to Washington [n9xhJrPXop4].mp4` ([D47](#d47)). The title keeps the library browsable, and the ID, which yt-dlp returns from the same metadata request as the title, keeps videos with equal or equally truncated titles apart. One rule in `downloaders/utils.py` names standalone video and caption downloads; the combined download derives its SRT path from the video path, so a video and its captions share a stem. OS-reserved characters in the title and ID are replaced, and pathlib-extensions' `build_filename` truncates only the title, at a UTF-8 character boundary, so the whole name fits in 220 bytes and the ID tag and suffix always survive ([D46](#d46)). A title with no character left to keep, such as an empty one, raises `ValueError`.

Files downloaded before IDs were added are named after the title alone. When the ID-tagged name does not exist but such a title-only file does, it is reused under its old name, so earlier downloads are not repeated. That match is by title alone and can still pair a different video with the same title with an existing file; the user accepted this for files that already exist. A title-only name ending in an 11-character ID-shaped tag that is not this video's own ID, such as `Title [aaaaaaaaaaa].mp4` for a video titled `Title [aaaaaaaaaaa]`, is never reused, because it can be another video's ID-tagged file; an old file of a video whose real title ends that way is downloaded again under the new name. No files are renamed.

Video downloads run inside a `StagedFile`, whose freshly created hidden `.staging-<random>` directory sits beside the resolved destination. yt-dlp writes a fixed `video.mp4` there, the name the caller gives the stage file through `StagedFile`'s name option ([D49](#d49)). Titles never enter yt-dlp's output template, and percent signs in directory components are escaped, so publication honors the literal requested filename. A parent path that yt-dlp would change through environment-variable or home expansion is rejected before creating the stage or constructing the downloader; variables in the title do not impose that limitation. Only a regular staged file after successful download and downloader context exit permits atomic publication. Failed downloads and interruption unwinding preserve previous output and remove the owned stage directory, including partial downloads and auxiliary files.

An abrupt process exit may leave a hidden `.staging-<random>` directory; automatic scavenging and power-loss durability are outside this behavior. Ordinary API glob patterns cannot enqueue files inside hidden stages, and media cleanup does not select those directories, though asset listing may show them. Each invocation gets an empty stage, so yt-dlp cannot reuse an old final file or resume a stale partial download.

### SRT as the output format

SRT was chosen to match an existing library of subtitle files. Engine-neutral timestamp/text conversion, SRT serialization and deduplication live in `adaptors/srt_deduplicator.py`. The public Whisper and Azure converters retain native segment handling; Azure converts its offset/duration ticks to seconds without importing Whisper for formatting. Shared formatting rounds total milliseconds before decomposition, always includes hours, uses comma milliseconds, and strips outer text whitespace before splitting on newlines. Supporting another output format (e.g. WebVTT, JSON) would mean adding a sibling serializer next to `save_segments_as_srt`.

SRT saving, caption download, and in-place deduplication publish through `publish_srt_text`: complete text is written to an exclusively created file inside a `StagedFile` and closed before atomic publication. A failed write, close, or publication preserves the prior valid SRT; a process interrupted before publication cannot expose a partial final file. Whisper's lazy segments are fully consumed and checked before staging, and in-place deduplication reads its input before publication. The existing-output policy is checked before expensive model/network work and reused for publication.

Video, SRT, and WAV publication share the same completion contract. pathlib-extensions' `StagedFile` owns the shared steps (target resolution, mode retention, stage creation, create-if-absent or replacement, and cleanup), each caller writes its output inside it, and `youtube_whisperer.overwrite.resolve_output_path` owns the existing-output preflight through the library's `OverwritePolicy.resolve` ([D48](#d48)). This project imports nothing else from the library's publication internals. Public functions accept only the `OverwritePolicy.ALWAYS` and `NEVER` members; any other value, including `RENAME`, a stale `OverwriteMode` member or a plain string, raises `ValueError` before any work, at each public entry point, because the library publishes such values as numbered copies that would break MP4/SRT pairing ([D48](#d48), [D49](#d49)). The SRT helpers in `adaptors/srt_deduplicator.py` default to `ALWAYS` ([D49](#d49)), `download_video` has no default, and every other public function with an overwrite parameter defaults to `NEVER`, the workers' policy. `NEVER` preserves existing output, including a competing file created during staging, using same-filesystem hard-link create-if-absent on Linux. A publication collision is skipped only when the destination is a file, including a symlink to a file; a late directory or dangling symlink propagates `FileExistsError` and removes the stage directory. Unsupported hard-link errors also propagate and remove the stage directory, without a fallback that could overwrite competing output. Approved replacement follows symlink targets and preserves existing mode bits; new SRT and WAV files use ordinary 0666 permissions filtered by the inherited umask, while new videos retain the downloader's file permissions. Replacement creates a new inode, so hardlinked aliases retain old contents and ownership, ACLs, and extended attributes may change.

This protects completion markers from process interruption, without guaranteeing durability across power loss. An abrupt exit may leave a hidden `.staging-<random>` directory beside the output; automatic scavenging is outside this behavior. Every publication gets its own newly created stage directory, and cleanup removes only that directory, so other writers' files are never touched. Existing legacy SRTs are still treated as complete under `NEVER`, without retroactive validation or repair.

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d8"></a>D8 | Preserve deduplication that bridges silent gaps between consecutive identical text; that behavior is intentional. | `yield_deduplicated_srt_blocks` |
| <a id="d15"></a>D15 | Empty decoded audio must be reported as a failed task rather than acknowledged without output. | NB23; supersedes the documented successful skip |
| <a id="d22"></a>D22 | Publish completed artifacts by atomic inode replacement, preserving ordinary permission bits and following symlink targets. Hardlinked aliases retain the old contents; ownership, ACLs, and extended attributes may change. The user accepted these metadata limits because an interrupted write must not expose a false completion marker or truncate prior valid output. Scope is process interruption, without power-loss durability or stale-stage scavenging. | Video, SRT, and WAV publication (implemented) |
| <a id="d47"></a>D47 | The user decided (2026-10-14) to name default downloads `Title [videoID].ext`, so equal titles, sanitization collisions and truncation collisions can no longer make two videos share a file, while the library stays browsable by title. ID-only names were rejected for losing browsability, and adding the ID only on collision for needing ownership metadata the project does not keep. Existing title-only files are not renamed: when the ID-tagged name is absent and a title-only file exists, it is reused, which avoids repeated downloads but keeps title-only aliasing for those existing files. A one-off rename script was rejected because files that already collided cannot be told apart. After review showed that a title ending in another video's tag, such as `Title [aaaaaaaaaaa]`, would match that video's new ID-tagged file as its title-only name, the user decided (2026-10-14) that a title-only name ending in an 11-character ID-shaped tag other than the video's own ID is never reused; the rare old file whose real title ends that way is downloaded again. | B5; `resolve_default_media_path` |

Consecutive identical subtitle blocks intentionally merge across silent gaps (D8). New default names include the video ID ([D47](#d47)); only reuse of a title-only file from before that change can still pair a video with another video's file.

## Deployment and configuration

### Operating envelope

Run exactly one YouTube worker, one Whisper worker per GPU, and as many Azure workers as the service concurrency limit allows. Parallel playlist expanders are not supported. All workers and the API must see compatible filesystem paths. The media library is persistent application data, and the Whisper model remains resident per process. [README](README.md#configuration) lists environment variables and launch commands.

### Build helpers come from a shared repository

The `apt` and `pip` steps of the image build live in [`docker-build-common`](https://github.com/liboyin/docker-build-common), not in this repo. They used to be local `docker_apt_install.sh` / `docker_pip_install.sh` scripts, copy-pasted across several projects and hand-synced, which drifted — fixes reached some repos and not others.

Compose supplies the helpers as a named build context (`build_common`) pinned to a version tag, and the Dockerfile bind-mounts that context for the length of each `RUN`. Bind-mounting rather than `COPY` keeps them build-time only: nothing is added to a layer and nothing ships in the image. `BUILD_COMMON_CONTEXT` overrides the pinned URL with a local clone, which avoids fetching that helper context and allows testing a helper change before it is tagged; other image-build steps still need their dependencies.

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d10"></a>D10 | Opening the devcontainer is intended to start the application workers against the configured queue and volumes. | Development startup; automated-test ownership rules still apply |
| <a id="d14"></a>D14 | Document current configuration behavior: Compose injects `.env`, direct invocations need exported variables, and fresh Compose setup must create the required file. Do not add automatic dotenv loading. | N7/N8 (closed) |
| <a id="d45"></a>D45 | The user decided (2026-10-12) to raise `requires-python` to `>=3.12` instead of determining the lowest compatible version or adding a CI version matrix. The source imports `typing.Self`, so 3.10 was never supported, and 3.12 is the only version any repository environment runs: the devcontainer and the Ubuntu 24.04 image's system `python3`. Ruff infers its target version from this floor, so `runtime.py` imports `Self` from `typing` instead of the undeclared `typing_extensions`. Supporting an older version would need its own verification. | NB3 (closed); [README local install](README.md#local-install) |
| <a id="d46"></a>D46 | **Superseded in part by [D48](#d48)**, which moved publication to the library's `StagedFile` and removed the `youtube_whisperer.publication` forwarder. The user decided (2026-10-13) to move generic path utilities from this project to [pathlib-extensions](https://github.com/liboyin/pathlib-extensions), whose `OverwriteMode` and `prepare_output_file` they already build on, in this order. (1) `truncate_filename` keeps only the trailing run of extension-like suffixes (a dot followed by ASCII letters or digits, such as `.tar.gz` or `.mp4`) and truncates everything else as stem text, so a long title containing a dot no longer raises and a long name without a suffix no longer returns its parent directory. (2) The low-level publication functions (`resolve_publication_target`, `publish_staged_file`) and one shared overwrite-preflight helper move to the library. A full create-publish-clean-up context manager waits for a second consumer, because this project's callers own documented stage names and fault-injection tests. (3) Title-to-filename construction moves after the B5 naming decision. Library messages keep using `print()`. The user pushes library commits; this project updates its commit pin only after that push, and `youtube_whisperer.publication` stays as a compatible forwarder under [D18](#d18). | NB36, NB37, B5 |
| <a id="d48"></a>D48 | **Superseded in part by [D49](#d49)** for the SRT helpers' defaults. The user decided (2026-10-22) to adopt pathlib-extensions `fff2bf6`, whose `OverwritePolicy` (`ALWAYS`, `NEVER`, `RENAME`) replaces `OverwriteMode`. `PROMPT` is removed because a web app cannot ask for consent. Every public function that defaulted to `PROMPT` now defaults to `NEVER`, the policy the workers already use, and accepts `OverwritePolicy` only: a hard break of [D18](#d18) for these parameters, because the library will remove `OverwriteMode`. `RENAME` raises `ValueError` here: in the library it now writes a numbered copy such as `Title [id].1.mp4`, and a numbered SRT beside its video would break the MP4/SRT pairing that asset cleanup and `ls_mp4_without_srt.sh` rely on; nothing in the application used it. Video, SRT and WAV publication move to the library's `StagedFile`, superseding the part of [D46](#d46) that deferred a context manager until a second consumer needed one. The library will deprecate and then remove `OverwriteMode` and its `publication` module after this migration, so this project imports neither: the `youtube_whisperer.publication` forwarder is removed, superseding its D18 forwarding clause in D46; its commits were never pushed. | NB38, NB39, NB40 |
| <a id="d49"></a>D49 | The user decided (2026-10-23), after the D48 gap review, four follow-ups. (1) `require_supported_policy` accepts only the `OverwritePolicy.ALWAYS` and `NEVER` objects and raises `ValueError` for anything else, because the library routes every other value, including stale `OverwriteMode` members and plain strings, to its numbered `RENAME` path; this supersedes NB38's accepted absence of a runtime check, and mypy still guards typed callers. (2) `save_segments_as_srt` and `deduplicate_srt_file` default to `ALWAYS`, like `publish_srt_text`, so the whole SRT module shares one default and in-place deduplication works without an explicit policy; this supersedes D48's `NEVER` default for those two functions only, and the in-repository callers already pass explicit policies. (3) The Azure worker reuses a sidecar WAV through `save_as_wav_file(..., NEVER)` instead of its own existence check, so the source must now exist even when its WAV does. (4) pathlib-extensions gains a stage-file name option on `StagedFile`, which video and WAV publication adopt after the user pushes it; the library marks `OverwriteMode` and its `publication` module deprecated without removing them yet. A library staged text writer was declined. | NB42–NB45 |

## Engineering governance

These decisions record accepted policy and its rationale; [AGENTS](AGENTS.md), the [review skill](.agents/skills/adversarial-review/SKILL.md) and the [group workflow](.agents/skills/grouped-task-execution/SKILL.md) own current requirements and procedures. Historical supersessions below do not reactivate retired requirements. Automated tests must remain isolated from live services, models and host data.

### Validation and coverage

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d1"></a>D1 | Tests are not type-checked. The mypy gate covers `youtube_whisperer` only, and widening it is not planned work. | mypy gate |
| <a id="d4"></a>D4 | `check-coverage.sh` owns the executable coverage policy. `pyproject.toml` keeps the pytest and aggregate coverage configuration. | Coverage policy |

### Tooling and review

| ID | Accepted decision and rationale | Applies to |
|---|---|---|
| <a id="d28"></a>D28 | **Superseded in the respects stated below.** Established valid scratch execution, invariant-based evidence, content-based baseline reuse and retained records. D29 supersedes permission handling; D34 refines validation cost and record requirements. | [AGENTS validation](AGENTS.md#validation-and-review); [review skill](.agents/skills/adversarial-review/SKILL.md) |
| <a id="d29"></a>D29 | Assume Full Access/bypass in the devcontainer while respecting enforced platform policies and preserving secret, host-data and test-ownership protections; supersedes D28's dispatch troubleshooting. | [AGENTS scope](AGENTS.md#scope-and-decisions) |
| <a id="d30"></a>D30 | Claude Code dispatches adversarial review through the standalone Codex CLI; Codex uses its native subagent tools. The devcontainer installs standalone Codex through its native installer; installer-owned commands and shell PATH setup replace the Claude Code plugin prerequisite, extension binary discovery and repair hooks. | [Reviewer dispatch](.agents/skills/adversarial-review/SKILL.md#reviewer-session); [devcontainer setup](README.md#dev-container-recommended) |
| <a id="d31"></a>D31 | **Superseded in the respects stated below.** Introduced reviewer continuity instead of fresh per-fix and separate Astra group reviewers. D34 supersedes the session-wide requirement with task/group continuity and optional replacement. | [Reviewer lifecycle](.agents/skills/adversarial-review/SKILL.md#reviewer-session) |
| <a id="d32"></a>D32 | Retain cosmetic reuse and delta-based follow-ups with full gates after non-trivial fixes. D34 supersedes mandatory additional group review. | [Review scope](.agents/skills/adversarial-review/SKILL.md#review-scope) |
| <a id="d33"></a>D33 | Require scratch copies for writable execution, not source/diff inspection or retained evidence output. | [Review procedure](.agents/skills/adversarial-review/SKILL.md#procedure) |
| <a id="d34"></a>D34 | The user approved proportionate governance to reduce validation and review overhead: targeted mutation evidence for high-impact invariants and removed/weakened coverage, relevant baselines with full gates for broad/uncertain baselines and substantive final candidates, one review per independent commit or cohesive combined change, additional group review only for uncovered integration risks, task/group reviewer continuity, compact records with detailed provenance for optional reuse, and justified non-blocking deferrals without routine approval. This supersedes the broader mutation mandate, full-baseline mandate, D31's session-wide lifecycle, D32's unconditional group review and mandatory user disposition of every non-blocking finding. Material decisions still require confirmation; test isolation, independent review and unresolved-blocker protections remain. | [AGENTS.md](AGENTS.md); [review skill](.agents/skills/adversarial-review/SKILL.md); [group workflow](.agents/skills/grouped-task-execution/SKILL.md) |
| <a id="d35"></a>D35 | Refine D34 after NB6/NB7: allow one implementation agent for coupled tasks sharing code, one authoritative task boundary, one primary producer of mutation evidence with independent verification and required additions or reruns, and compact reports without duplicated logs or empty sections. Required gates, independent review, isolation, integrity checks and finding dispositions remain. | [Group workflow](.agents/skills/grouped-task-execution/SKILL.md); [review skill](.agents/skills/adversarial-review/SKILL.md); TODO maintenance |
| <a id="d36"></a>D36 | The user requested governance improvements after NB27/NB28/N12. The resulting policy was committed as `3afac8a`. Refine D34/D35 with an explicit candidate-freeze handoff, invariant-based evidence for consolidated tests, mutation containment under changed control flow, affected-case reruns for scratch-only corrections, and concise evidence retention with storage lifetime disclosure. Whole-batch reruns are not a policy requirement for scratch-only probe corrections. The user accepts temporary evidence storage with disclosed lifetime limits for this project. Required application gates, independent review and test ownership remain. | [AGENTS test guidelines](AGENTS.md#test-guidelines); [group workflow](.agents/skills/grouped-task-execution/SKILL.md); [review evidence](.agents/skills/adversarial-review/SKILL.md#evidence-retention); [scratch execution](.agents/skills/adversarial-review/references/scratch-testing.md) |
| <a id="d37"></a>D37 | Closing a TODO task archives its boundary, disposition, evidence, review results and limitations in `completed_work/<ID>.md`, with a one-line TODO index entry in the same commit. This refines D36's temporary-storage allowance: working evidence may be temporary with disclosed lifetime limits, but essential completion evidence must persist in the archive or durable linked artifacts. | [TODO maintenance](TODO.md#maintaining-this-plan); [review evidence](.agents/skills/adversarial-review/SKILL.md#evidence-retention) |
| <a id="d40"></a>D40 | The user requested governance refinements after NB18/NB19/NB24. Implementation agents use the active harness's own subagent mechanism; the earlier group-workflow text assigning them `gpt-6.1-sol` was unintended, and that model remains fixed only for the reviewer. Claude Code reviewer dispatch through the standalone Codex CLI (D30) closes stdin so `codex exec` starts. Task boundaries name the affected compatibility surface, so D18 public APIs are checked before implementation rather than at review. Scratch runs retain one provenance summary line and failure excerpts instead of full passing logs. Tasks closed by one cohesive commit may share one full completion record. Required gates, independent review, isolation, evidence archival and finding dispositions remain. | [Group workflow](.agents/skills/grouped-task-execution/SKILL.md); [reviewer dispatch](.agents/skills/adversarial-review/SKILL.md#reviewer-session); [scratch recipe](.agents/skills/adversarial-review/references/scratch-testing.md); TODO maintenance |
| <a id="d41"></a>D41 | Following the review of `48fff69`, the user requested implementation of the governance recommendations, then the Python snapshot rewrite with project tests and coverage. Plan commit boundaries before grouped implementation and link shared completion evidence while retaining candidate-specific results. Include advisory governance feedback in Close ([D44](#d44) moves it to the final report-and-reflect step); reflection does not authorize edits to governance or skills unless the user asks. Keep the snapshot helper skill-owned and outside the application package, using standard-library Python and deterministic JSON to preserve index fingerprints, symlink non-traversal and unusual filenames. Before any working-tree scan it refuses an index containing submodules or tracked paths below a working-tree symlink, because Git would then reach outside the root index; this repository has no submodules, and supporting them would need a separate design. File-based test loading and project coverage make the helper testable without application coupling. Required validation, review and evidence safeguards remain. | [Group workflow](.agents/skills/grouped-task-execution/SKILL.md); [TODO maintenance](TODO.md#maintaining-this-plan); [snapshot helper](.agents/skills/adversarial-review/references/snapshot.py); [test standards](AGENTS.md#test-guidelines); [test procedures](README.md#testing) |
| <a id="d44"></a>D44 | After the API group (N1/NB29/NB15), the user asked for a main-agent gap review independent of the adversarial-review skill, had its gaps fixed (NB35, N13) and the review repeated, then asked for that step to be added to the group workflow before the reflection. The workflow now closes with a gap review of the committed range followed by a separate report-and-reflect step; this moves the reflection out of Close, superseding D41 only in that placement. Gaps do not expand authorization: they are reported before fixing unless the user has asked for fixes, and fixes follow the normal boundary, gate, review and archival rules. | [Group workflow](.agents/skills/grouped-task-execution/SKILL.md) |

### Documentation ownership

The user requested this split: DESIGN owns design, product contracts and decisions; README owns usage; TODO owns future work. It fulfills NB4 with DESIGN rather than a separate USER_STORIES document. D2, D3 and D7 were removed by the user and are not restored here; gaps in the identifiers are intentional. No cross-project governance synchronization requirement is carried forward.
