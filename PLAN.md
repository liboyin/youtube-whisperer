# youtube-whisperer: Comprehensive Review & Improvement Plan

## Context

Full review of the project (all 28 source files, all 21 test files, Docker/compose/devcontainer infra, docs), followed by an improvement plan scoped to the project's designed purpose: a personal, LAN-hosted YouTube download + transcription service with a filesystem media library.

Current state verified: **193 tests pass, 95.4% branch coverage, mypy and ruff clean.** The codebase is in good shape overall — small functions, consistent docstrings, real dead-letter/PEL recovery semantics with tests that encode *why*. The findings below are what's left.

Decisions already made:
- `ISSUES.md`: deletion is intentional — its still-open item (XAUTOCLAIM sweeper) is migrated into this document (finding 5 / Phase 3).
- Scope: **everything** (correctness + architecture + infra/docs).

---

## Review Findings

### A. Correctness & security bugs

1. **Whisper failures never reach the dead-letter queue.** `WhisperWorker.dispatch_task` (`workers/whisper_worker.py:76`) calls the CLI helper `transcribe_to_srt_files` (`__main__.py:37`), which calls `transcribe_file_with_default_model` (`transcriber/whisper_transcriber.py:95-104`) — and that swallows `RejectedTranscriptionError` *and all `Exception`s*, returning `None`. The worker sees no exception, so every failed Whisper task is XACK'd + XDEL'd as if it succeeded. Only waveform-load errors (raised before the `try`, line 91) dead-letter. The Azure worker, by contrast, raises properly. Silent data loss: queue says done, no SRT exists, nothing in `/dead-letters`.
2. **Path traversal in `POST /assets`.** `app.py:182` writes to `dir_path / upload.filename` with the client-controlled filename. A multipart filename like `../../home/ubuntu/.bashrc` writes outside the assets dir. Unauthenticated API ⇒ arbitrary file write.
3. **Packaging bug: `tests`, `assets`, `htmlcov` are packaged.** `pyproject.toml:54-55` uses `find = {where = ["."]}` with no include filter. Proof: `youtube_whisperer.egg-info/top_level.txt` lists `assets`, `htmlcov`, `tests`, `youtube_whisperer`. Also a stale nested `youtube_whisperer/youtube_whisperer.egg-info/` (references a defunct `formatters` package) should be deleted.
4. **`Task.source` default is evaluated once at import.** `fastapi/models.py:24`: `f'assets/{datetime.date.today().year}*.mkv'` — the year freezes at process start (stale after New Year on a long-running server), it's a personal-workflow glob baked into the public API contract, and a *defaulted* source means `POST /tasks` with `{}` silently globs the assets dir.
5. **Scaled workers collide on consumer identity.** `docker-compose.cpu.yaml` sets `WORKER_SLOT_ID: '1'` on every worker, so `--scale whisper_worker=2` yields two consumers both named `whisper-1` sharing one PEL — each recovers (and reprocesses) the other's in-flight task via the `0-0` read in `workers/common.py:43-54`. README's claim that "scaled worker containers naturally govern exclusive message queues" contradicts the compose config. Related known gap (migrated from ISSUES.md): no `XAUTOCLAIM` sweeper, so PEL entries owned by dead consumer names are stranded forever (shown as "active" in `GET /tasks` indefinitely).
6. **Playlist expansion is fragile and channels don't actually work.** `playlist_downloader.py:31` does `ydl.extract_info(url)['entries']` — `extract_info` can return `None`, entries can contain `None` for deleted/private videos (`v['id']` → `TypeError`). Routing is `'playlist' in url` (`:48`) — channel URLs (`/@handle`, `/channel/…`) never match, so they're treated as single videos and fail, despite README/docstrings claiming channel support.
7. **Azure timeout too tight for short audio.** `azure_transcriber.py:102`: `timeout = duration * 1.5` — a 10 s clip gets 15 s including Azure session startup; `duration == 0` times out immediately. Needs a floor.
8. **Redis host hardcoded.** `utils.py:16` pins `host='redis'`; not in `Settings`, not in README's config table — yet README documents running components directly outside compose, which can't resolve `redis`.
9. **`assert` used to validate external input.** `srt_deduplicator.py:37` (`SrtBlock.from_lines`) asserts on lines parsed from *downloaded* SRT files; `app.py:181` asserts on `upload.filename`. Both vanish under `python -O` and produce 500s/AssertionErrors instead of clean errors.
10. **Dead defensive branch.** `__main__.py:58-59`: the `case _` in `transcribe_to_srt_files` is unreachable (input already coerced via `TranscriberType(transcriber)` at line 49). Coverage confirms (lines 58-59 never hit).
11. *(Accepted, document only)* `clear_task_queues` (`queueing.py:195-196`) snapshots then deletes non-atomically — tasks enqueued in between are deleted unreported. Benign at this scale; document the race.

### B. Architecture & code hygiene

12. **Layering inversion: queue/worker layers import from the web layer.** `queueing.py:5` and `workers/common.py:8` import `Task` from `youtube_whisperer.fastapi.models`. Domain models belong in a neutral module.
13. **Package `youtube_whisperer/fastapi/` shadows the third-party `fastapi` name** — `from fastapi import …` inside `youtube_whisperer/fastapi/app.py` works only thanks to absolute-import rules; perpetually confusing.
14. **Worker imports the CLI entry module.** `workers/whisper_worker.py:8` imports from `youtube_whisperer.__main__` — entry point used as a library (same root cause as finding 1).
15. **`WhisperModel` is re-loaded for every task.** `whisper_transcriber.py:70` constructs the model per file — a multi-GB `large-v3` load per queue item on a dedicated GPU worker. Cache per process.
16. **`print()` everywhere instead of `logging`.** Workers, downloaders, transcribers all `print` (no levels, no timestamps); `fastapi/app.py` alone has a proper logger. Several tests assert on `capsys` output, coupling tests to log strings.
17. **Legacy `repr`-string parsing exposed via the API.** `lang_code_adaptor.py:74-94` + validator branch at `:129-130` accept `"LanguageCode(source='en')"` strings as API input — dead compatibility path with its own tests. (Redis payloads serialize via the `str` form, so removal is safe; note: any *ancient* dead-letter entries in Redis using repr form would fail to parse — clear dead letters at deploy.)
18. **Dead code:** `load_whisper_waveform_from_bytes` (`waveform_loader.py:10-49`, only tests use it) and `TranscriptBlock` TypedDict (`transcript_downloader.py:15-18`, zero uses).
19. **Test-layout drift:** `tests/test_worker.py` and `tests/workers/test___main__.py` both test `workers/__main__.py` (breaks the mirror-the-package convention); stale `mocker.patch('time.sleep')` in `tests/workers/test_common.py:29` (the sleep-based poller is gone); stale `scan_iter` stub in `tests/fastapi/test_app.py:20`.

### C. Infra, ops & docs

20. **`redis:latest` + `pull_policy: always`** — unpinned server image in "production"; the redis-py 8.0 timeout regression (see `utils.py` comment) shows this class of risk is real here.
21. **Personal machine baked into compose:** proxy IP `192.168.0.4` (build args), bind mounts `/media/libo-smallfiles/Transcode` and `~/snap/firefox/...` in `docker-compose.cpu.yaml:1-8`. `docker compose up` fails on any other machine. Also: `docker_apt_install.sh:6` / `docker_pip_install.sh:17` use `[ -v VAR ]`, which passes for *empty* build args — compose always sets them, so an empty value would write a broken proxy config.
22. **Dockerfile layer caching:** `COPY . .` before dependency install ⇒ every source edit reinstalls all pinned deps.
23. **`.dockerignore` mismatch:** ignores `docker-compose*.yml` but files are `.yaml`.
24. **No redis healthcheck** — workers race Redis at startup and rely on crash-restart.
25. **Zero auth on a destructive API** (`DELETE /tasks`, `DELETE /assets`, arbitrary-glob task sources, file upload) — acceptable for the designed LAN/home use, but the trust model is nowhere documented.
26. **`postCreateCommand.sh` regenerates `requirements.txt` via `pip freeze` on every container create** — the lock file mutates as a side effect of opening the devcontainer (source of the recurring "Updated dependencies" commits). Freezing should be an intentional act.
27. **README prose quality:** several architecture/design paragraphs are semantically garbled ("system tasks are managed frictionlessly by a unified consumer group topology", "extract their outstanding debts identically", "mapping stream architectures recursively onto standard abstract layers" — nothing is recursive). Undocumented design choices: the language whitelist is exactly `{en, en-us, zh, zh-cn}` (`lang_code_adaptor.py:8`); the rejection list is two hardcoded Chinese hallucination phrases; filename truncation at 220 chars; per-module `main()` CLIs; stale "YouTube active-slot policy" phrasing.

---

## Implementation Plan

Conventions for every step: Google-style docstrings on new/changed functions; tests mirror source order and use `import … as testee`; after each change run `pytest && mypy youtube_whisperer && ruff check .` and keep every file ≥80% branch coverage; one commit per functionally independent change, message format `Claude: <summary>` + one paragraph (no Co-Authored-By).

### Phase 0 — Repo bookkeeping
1. Commit the pending dependency bumps in `requirements.txt`.
2. Commit the `ISSUES.md` deletion together with this document, which absorbs its still-open items (findings 5 and 11). Swap `ISSUES.md` for `PLAN.md` in `.dockerignore`.

### Phase 1 — Correctness & security (one commit each)
3. **Whisper dead-letter fix + de-layering (findings 1, 10, 14).** Refactor `transcribe_file_with_default_model` to *raise* on failure (keep the `None`-for-skipped-empty-waveform / existing-file returns); move the catch-and-print into the CLI loop `transcribe_to_srt_files` so CLI behavior is unchanged; delete the unreachable `case _`. Change `WhisperWorker.dispatch_task` to call the transcriber directly (no more `__main__` import) so exceptions propagate to `BaseWorker.process_queue` and dead-letter. Tests: worker test asserting a Whisper failure dead-letters; CLI tests keep asserting the printed failure.
4. **`POST /assets` traversal fix (findings 2, 9b).** In `app.py:add_assets`, reject uploads whose filename is missing or whose resolved target escapes the assets dir (`Path(name).name` sanitization + `resolve().is_relative_to(...)` check) — such files go to `failed`, no assert. Tests: traversal attempt lands in `failed` and writes nothing.
5. **Packaging fix (finding 3).** `[tool.setuptools.packages.find] include = ["youtube_whisperer*"]`; delete both stale egg-info trees from the working directory. Verify with a wheel build that only `youtube_whisperer` is packaged.
6. **Make `Task.source` required (finding 4).** Drop the dynamic default; update the docstring and the handful of tests constructing `Task()` bare (`tests/test_queueing.py`, `tests/fastapi/test_models.py`, …). Document the API change in README.
7. **Robust playlist/channel expansion (finding 6).** In `yield_video_urls_from_playlist` / `yield_flattened_video_urls`: drop the `'playlist' in url` substring heuristic; extract with `extract_flat`, branch on whether the result contains `entries` (multi-video: playlist/channel/tab) or not (single video), skip `None` entries, and raise a clear error when extraction returns nothing. This makes channels actually work as documented.
8. **Azure timeout floor (finding 7).** `max(60.0, duration * 1.5)` with the constant named and documented.
9. **Configurable Redis endpoint (finding 8).** Add `redis_host`/`redis_port` to `Settings` (defaults `redis`/`6379`), use them in `utils.py`; README config table rows.
10. **`SrtBlock.from_lines` input validation (finding 9a).** Replace the assert with a `ValueError` naming the offending block.

### Phase 2 — Architecture & hygiene (one commit each)
11. **Move domain models out of the web layer; un-shadow `fastapi` (findings 12, 13).** New `youtube_whisperer/models.py` holding `Task`, `TaskQueues`, `DeadLetter`, `AddTasksResponse`, `AddAssetsResponse`; rename `youtube_whisperer/fastapi/` → `youtube_whisperer/api/` (only `app.py` remains in it). Update all imports, the compose `entrypoint` (`youtube_whisperer.api.app:app`), README structure/commands, and mirror the move in `tests/` (`tests/test_models.py`, `tests/api/test_app.py`).
12. **Cache the Whisper model per process (finding 15).** `@functools.lru_cache` factory (`get_default_whisper_model()`) reading settings inside; document in README that the GPU worker keeps the model resident by design.
13. **Adopt `logging` (finding 16).** Module loggers everywhere; `logging.basicConfig` in the two entry points (`workers/__main__.py`, `__main__.py`); `logger.exception` where tracebacks matter (worker loop, transcribers); keep user-facing CLI result lines as `print`. Migrate `capsys` assertions to `caplog` where output moved.
14. **Remove legacy/dead code (findings 17, 18).** Delete `LanguageCode.from_repr` + validator branch + its tests (note in commit message: pre-existing repr-form dead letters in Redis, if any, must be cleared); delete `load_whisper_waveform_from_bytes` and `TranscriptBlock` with their tests.
15. **Test cleanup (finding 19).** Merge `tests/test_worker.py` into `tests/workers/test___main__.py` ordered to match the source; drop the stale `time.sleep` patch and `scan_iter` stub.

### Phase 3 — Queue robustness under scaling (one commit)
16. **Unique consumer names + orphan recovery (finding 5).** Remove `WORKER_SLOT_ID` from the compose worker services so the hostname fallback gives scaled replicas unique consumer names. Add an `XAUTOCLAIM` pass to `yield_task` (before the blocking read): claim messages idle longer than a new `worker_claim_min_idle_seconds` setting (default conservatively above the longest plausible transcription, e.g. 6 h) so tasks stranded by dead consumer identities are recovered instead of pinned "active" forever. Tests for the claim path; README: update Known limitations + Operational Notes + config table.

### Phase 4 — Infra & docs (one commit each)
17. **Compose/Dockerfile hardening (findings 20-24).** Pin `redis` to a major version and drop `pull_policy: always`; parameterize `APT_PROXY`, `PYPI_PROXY`, assets dir, and Firefox-profile mount via `.env`-driven variables with working defaults (`./assets` etc.); fix the `[ -v … ]` guards to `[ -n "${VAR:-}" ]`; add a redis healthcheck + `depends_on: condition: service_healthy`; fix `.dockerignore` glob to `.yaml`; reorder the Dockerfile (copy `requirements.txt` + install scripts → install deps → copy source → editable install) for layer caching.
18. **Stop auto-freezing the lock file (finding 26).** Move the `pip freeze` line from `postCreateCommand.sh` into a small `update_lock.sh` run intentionally; README documents the workflow.
19. **README overhaul (findings 25, 27 + all doc deltas above).** Rewrite the garbled architecture/design paragraphs in plain English; add a short **Security / trust model** note (unauthenticated, LAN-only by design); document the language-code whitelist (and how to extend it), the rejection list's purpose, filename truncation, per-module CLIs; remove stale "active-slot policy" phrasing; refresh the structure tree and config table for everything moved/added in Phases 1-3; document the `clear_task_queues` snapshot race (finding 11) as a known benign limitation.

## Verification

- After every commit: `pytest` (≥80% per-file branch coverage via `--cov-report=term-missing`), `mypy youtube_whisperer`, `ruff check .`.
- Targeted proofs: wheel build lists only `youtube_whisperer*` (step 5); curl a traversal filename against `POST /assets` and confirm `failed` + no file (step 4); induce a Whisper failure (rejection phrase via mocked segments) through a real worker loop and confirm the dead letter (step 3).
- End-to-end smoke after Phase 4: `docker compose -f docker-compose.cpu.yaml up` on defaults (no personal paths), `POST /tasks` with a filesystem glob, watch the whisper worker consume, `GET /tasks` / `GET /dead-letters` behave, `docker compose up --scale azure_worker=2` shows distinct consumer names.
