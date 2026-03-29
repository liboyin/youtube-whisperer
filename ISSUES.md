This document is intended for AI agents to document issues and antipatterns found during code reviews. Note that not all of them are genuine issues - some might be design choices.

# 1. Critical Concurrency & Architecture Flaws

## 1.1 Non-Atomic YouTube Queue Processing (Rejected: intentional single-worker recovery behaviour)
**File:** `workers/youtube_worker.py` -> `process_queue()`, `workers/common.py` -> `yield_task()`
* **Issue:** [RESOLVED] The YouTube worker used to use list peeks for `tasks:youtube`, but it now consumes `stream:youtube` purely using horizontal scaling natively over Redis Consumer Groups.
* **Design rationale:** Whisper, Azure, and YouTube tasks all use Consumer Groups natively locking messages asynchronously to execution pods (e.g. `gpu-0`).

## 1.2 Redis Connection Exhaustion (Addressed)
**File:** `utils.py` -> `get_redis_client()`
* **Issue:** `get_redis_client()` instantiates a completely new `redis.StrictRedis` client without utilizing a connection pool. It also executes a `.ping()` for health checking per instantiation.
* **Impact:** `fastapi/app.py` uses `Depends(get_redis)` for every API endpoint. This means every single HTTP request will initiate a new TCP connection to Redis and perform a ping, severely degrading API throughput and potentially exhausting TCP source ports under load (TIME_WAIT states).
* **Recommendation:** Create a single global `ConnectionPool` mapped to a cached `Redis` client instance, and reuse it across requests.

# 2. Web API (FastAPI) Antipatterns

## 2.1 Blocking I/O in Async Endpoints (Addressed)
**File:** `fastapi/app.py`
* **Previous issue:** `add_tasks()` used to expand playlist URLs inside FastAPI, which meant `yt-dlp` network I/O ran in request handlers.
* **Fix:** URL tasks are now queued directly to `stream:youtube`, and the dedicated YouTube worker performs playlist expansion, downloads, and transcript fetching. FastAPI still resolves filesystem globs because that work is cheap and does not require network I/O.
* **Resolved concern:** `add_assets` previously read the entire file upload into memory before writing it synchronously. Fixed by replacing `await upload.read()` + `f.write(content)` with `shutil.copyfileobj(upload.file, f)`, which streams directly from the upload to disk in fixed-size chunks.

# 3. Worker & Subsystem Antipatterns

## 3.1 Azure Task Completion Is Not Durable (Addressed)
**File:** `workers/azure_worker.py` -> `dispatch_task()`, `workers/common.py` -> `process_active_slot_queue()`
* **Previous issue:** Azure work used to submit transcription to a background thread and immediately remove the Redis task. Late Azure failures were only printed.
* **Fix:** Azure workers now consume a task into their PEL dynamically inside `stream:azure` and call `transcribe_audio_file()` synchronously. The task is removed from Redis only after completion (via `XACK`), or dead-lettered on failure.

## 3.2 Polling / Busy Waiting (Rejected: design choice)
* **Issue:** `workers/common.py` -> `yield_task()` and `yield_active_slot_task()` poll Redis using `time.sleep(poll_interval)`.
    * *Recommendation:* Use Redis blocking operations natively (`BLPOP`).

## 3.3 Expensive Eager File Checks (Fixed)
**File:** `downloaders/utils.py` -> `is_firefox_cookies_available()`
* **Issue:** Uses `Path(...).rglob('cookies.sqlite')` on massive home directories like `~/.mozilla/firefox`.
* **Impact:** This is executed synchronously *every time* `download_video` or `playlist_downloader` is invoked. Traversing the entire Firefox directory structure recursively can be extremely slow and blocking.
* **Fix:** Added `@functools.lru_cache` to `is_firefox_cookies_available()`. The `rglob` search now runs at most once per process lifetime; subsequent calls return the cached result immediately.

## 3.4 Missing Auto-Scale Down Support (TODO)
* **Issue:** Redis Streams consumer groups inherently require workers to explicitly clean up their PEL debts. When an orchestration platform implicitly scales the worker fleet *down*, pods are destroyed dynamically. Without a centralized process leveraging `XAUTOCLAIM` (or `XPENDING` -> `XCLAIM`) to periodically sweep tasks historically locked by `consumer_name` bindings that no longer exist, tasks get permanently orphaned inside Redis.
* **TODO:** Implement an `XAUTOCLAIM` loop (perhaps routinely scheduled inside FastAPI or within individual workers) to gracefully handle scaling down ephemeral GPU/CPU containers without stranding work.

# 4. General Python Best Practices

* **Overuse of `print` vs `logging`:** Across the entire codebase, `print()` is heavily used for tracking state and errors. Logs lack structured data, log levels (INFO, WARN, ERROR), and timestamps. Switching to the standard `logging` library or `loguru` is highly advised.
* **Swallowed Tracebacks:** Several `try/except Exception as e:` blocks exist (e.g., in `workers/common.py`, `workers/youtube_worker.py`, or `whisper_transcriber.py`) where only the error message is printed. The traceback is vital for debugging offline workers. Use `logging.exception("...")`.
* **Memory Inefficiencies**: Yielding lazy iterators correctly exists (e.g., in `WhisperSegmentAdaptor`), but `deduplicate_srt_file` explicitly materializes it into memory using `blocks = list(...)` to eagerly close a file handle. It defeats the purpose of the layered generators below it if the file is large, though SRTs are relatively small.
