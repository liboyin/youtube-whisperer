# YouTube Whisperer

`youtube-whisperer` downloads YouTube videos, playlists and channels, fetches existing captions, and transcribes local media into SRT subtitles through a FastAPI service. The asset directory is a human-browsable media library and the source of truth for completed work.

Whisper runs locally through `faster-whisper` on an NVIDIA GPU or CPU (default model: `large-v3`, approximately 9 GB RAM/VRAM). Azure Speech provides a cloud transcription option. Dedicated workers use Redis Streams for assignment, recovery and dead-letter reporting.

See [DESIGN.md](DESIGN.md) for architecture, product contracts and topic-grouped user decisions; [TODO.md](TODO.md) for future work; and [AGENTS.md](AGENTS.md) for contribution standards.

## Security / trust model

The API is **unauthenticated by design** for a trusted LAN or single-user deployment. Any reachable client can submit filesystem globs and call destructive endpoints such as `DELETE /tasks` and `DELETE /assets`. Do not expose it directly to the public internet; use a VPN, an authenticated reverse proxy, or a firewall.

## Build & Run

### Prepare the Compose environment

Before opening the devcontainer or starting Compose, create the required ignored file from the repository root:

```sh
touch .env
```

This preserves an existing file's contents. An empty file is sufficient for non-Azure use; add `AZURE_SPEECH_API_KEY` and `AZURE_SERVICE_REGION` to use Azure. Review the host path settings in [Configuration](#configuration) before startup: the devcontainer intentionally starts workers against the configured queues and mounted volumes.

### Dev Container (recommended)

Open the repository in VS Code and reopen in the Dev Container (`.devcontainer/`). The image installs the pinned dependencies from `requirements.txt` and the project. The creation hook then rewrites `requirements.txt` from the installed environment, installs the editable project's dev extras, and installs Claude Code and standalone Codex with their native installers. Codex installation is noninteractive; its installer owns command installation and shell PATH setup, and the hook verifies `codex --version`. Review tooling needs no Claude Code plugin or VS Code extension binary links. Sign in with `codex login` before using direct CLI review; [the review skill](.agents/skills/adversarial-review/SKILL.md#reviewer-session) owns dispatch and authentication checks.

### Full stack with Docker Compose

```sh
docker compose up                              # GPU (NVIDIA runtime)
docker compose -f docker-compose.cpu.yaml up   # CPU only
```

This starts Redis, the API on port `8001`, and the YouTube, Whisper and Azure workers. Interactive API documentation is at `http://localhost:8001/docs`.

The build fetches shared helpers from GitHub at `docker-build-common` tag `v1.1.0`; set `BUILD_COMMON_CONTEXT` to a local clone to avoid fetching that helper context. Other image-build steps still need their dependencies. Compose supplies the named context automatically. A standalone build must supply it explicitly:

```sh
docker buildx build --build-context build_common=https://github.com/liboyin/docker-build-common.git#v1.1.0 .
```

See [build-helper design](DESIGN.md#build-helpers-come-from-a-shared-repository) for its ownership and rationale.

### Local install

Use the container's Python 3.12 environment as the reference. The package declares Python ≥3.10, but current source imports `typing.Self`, which is unavailable in 3.10; the supported minimum remains unresolved under NB3 in [TODO.md](TODO.md). Direct launches also need ffmpeg and a reachable Redis server (`REDIS_HOST`/`REDIS_PORT`).

```sh
pip install -r requirements.txt
pip install -e '.[dev]'
```

### Running components directly

```sh
# REST API
uvicorn youtube_whisperer.api.app:app --host 0.0.0.0 --port 8001

# Worker (choose one role)
python -m youtube_whisperer.workers {youtube|whisper|azure} [--slot ID] [--poll-interval-seconds N]
```

Direct launches read exported environment variables, not `.env`. Polling intervals must be positive integer seconds (default `5`); claim-idle seconds must be nonnegative. See [queue recovery](DESIGN.md#redis-streams-and-a-shared-consumer-group).

## Usage

Submit source-language transcription work, for example:

```sh
curl -X POST http://localhost:8001/tasks \
  -H 'Content-Type: application/json' \
  -d '[{"source":"/workspaces/youtube-whisperer/assets/*.mp4","transcriber":"whisper","language":"en-us"}]'
```

Use a YouTube URL as `source` to download and transcribe, or choose `"transcriber":"none"` for download only. Filesystem paths refer to the API's filesystem. Use BCP-47 `en-us` or `zh-cn` for either engine; Whisper also accepts `en` or `zh`. Translation and the old `mode` field are unsupported.

The API exposes `/tasks` (GET/POST/DELETE), `/dead-letters` (GET/DELETE), and `/assets` (GET/DELETE). See [HTTP contracts](DESIGN.md#http-contracts) for response shapes, clearing semantics and asset cleanup, and [upgrade guidance](DESIGN.md#transcription-requests-and-upgrades) for obsolete clients and persisted payloads.

## Configuration

Direct launches read exported environment variables. Compose injects `.env` into application services, but explicit service `environment` values take precedence: the CPU file sets `WHISPER_USE_CUDA=0`, and the GPU override sets it to `1` for the API and Whisper worker. Azure credentials are needed only for Azure transcription. Each API/worker runtime owns a settings snapshot; see [settings and resource ownership](DESIGN.md#settings-and-runtime-ownership) for Python callers and injected resources.

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
| `WORKER_SLOT_ID` | unset | Stable slot suffix: consumer name is `<role>-<value>`; without it, the hostname is used. `--slot` overrides both. |
| `WORKER_ROLE` | `whisper` | Default role when `python -m youtube_whisperer.workers` is run without one. |
| `WORKER_CLAIM_MIN_IDLE_SECONDS` | `21600` | Idle time before a worker claims a PEL entry stranded by another consumer. Must be nonnegative; zero permits immediate claims. Keep it above the longest plausible transcription. |

`.env` is git-ignored and injected into the four application services; Redis does not receive it. Keep credentials out of version control.

Compose also reads a few **interpolation** variables (host-side paths and build proxies) from your shell or `.env`, with defaults for the host paths:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ASSETS_DIR` | `./assets` | Host directory bind-mounted as the media library. |
| `WHISPER_MODELS_VOLUME` | `whisper_models` (named volume) | Host directory or volume for the Whisper model cache. |
| `FIREFOX_PROFILE_DIR` | `firefox_profile` (named volume) | Host Firefox profile for yt-dlp cookies; set it to download private/age-gated videos. |
| `APT_PROXY` | empty (none) | Optional apt caching proxy used during image build. |
| `PYPI_PROXY` | empty (none) | Optional PyPI proxy used during image build. |
| `BUILD_COMMON_CONTEXT` | pinned Git URL (`docker-build-common.git#v1.1.0`) | Shared build-helper source; a local clone avoids fetching that context. |

## Updating dependencies

`pyproject.toml` declares dependencies; `requirements.txt` is the frozen lock file. The devcontainer creation hook currently regenerates the lock before installing dev extras:

```sh
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
```

After changing dependencies and reinstalling, review and commit the regenerated lock file. Plain container recreation can also change it; deliberate lock refresh is future work under NB5 in [TODO.md](TODO.md).

## Testing

For non-trivial code, test or configuration changes, run the required gates before commit. [AGENTS.md](AGENTS.md#validation-and-review) owns baseline selection and documentation/cosmetic exceptions:

```sh
./check-coverage.sh
mypy youtube_whisperer
ruff check .
```

`check-coverage.sh` runs pytest and requires at least 80% statement and branch coverage for every measured file and the project. `COVERAGE_THRESHOLD` overrides the script threshold with a number from 0 to 100 inclusive; an empty value keeps 80, and any non-numeric, non-finite or out-of-range value fails before pytest runs. pytest also retains its configured aggregate floor. Pass only whole-suite options such as `-x` or `-q` to this gate; selected test paths cannot certify per-file coverage. Coverage includes the application and the standalone [review snapshot helper](.agents/skills/adversarial-review/references/snapshot.py). Its tests load the script as `testee` by file path and use owned temporary Git repositories; the helper stays outside the application package. Tests are intentionally outside the mypy gate.

Tests run in random order through `pytest-randomly`; reproduce an ordering failure with the printed `--randomly-seed=<seed>`. For focused checks, use `pytest --no-cov` to avoid the aggregate coverage failure caused by selecting only part of the suite.

[The test bootstrap](tests/conftest.py) owns temporary home, asset and model paths, synthetic settings and cleanup. Always start pytest in a fresh Python process; prior application-settings imports or repeated embedded `pytest.main()` calls are rejected. Tests must not reach external services, real models or host data; [AGENTS.md](AGENTS.md#test-guidelines) owns these protections.

## Operational Notes

- Run exactly one `youtube_worker`; parallel playlist expansion/download is unsupported.
- Run one `whisper_worker` per GPU; the model stays resident per process.
- Scale Azure workers within your Azure concurrency limit, for example `docker compose up --scale azure_worker=2`.
- Consumer names default to container hostnames. `WORKER_SLOT_ID` gives `<role>-<value>`; CLI `--slot` supplies the full name and takes precedence. Names must be unique among concurrent consumers of the same stream; leave `WORKER_SLOT_ID` unset for ordinary Compose scaling, or assign each replica its own value.
- Keep `WORKER_CLAIM_MIN_IDLE_SECONDS` above the longest expected processing time. Stranded tasks remain active until eligible for reclamation (default six hours).
- Queue and dead-letter clearing snapshots then deletes non-atomically; concurrent additions can be removed without appearing in the response. Clearing queues does not cancel work already running.
- Older persisted payloads may require manual Redis repair; see [upgrade guidance](DESIGN.md#transcription-requests-and-upgrades) before switching versions.

The repository also includes `extract_subtitle_text.sh` to print an SRT file's cue text without its indexes, timing lines or blank lines, from LF or CRLF input, and `ls_mp4_without_srt.sh` to find videos without sibling subtitles. Known defects and accepted limitations are tracked in [TODO.md](TODO.md) and [DESIGN.md](DESIGN.md).
