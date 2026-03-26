This document is intended for AI agents to document issues and antipatterns found during code reviews. Note that not all of them are genuine issues - some might be design choices.

# 1. Critical Concurrency & Architecture Flaws

## 1.1 Non-Atomic Queue Processing in Worker (Rejected: intentional design for GPU failure recovery)
**File:** `worker.py` -> `process_queue()` and `yield_task()`
* **Issue:** The worker uses `lrange('tasks', 0, 0)` to read a task, processes it (which could take minutes), and then calls `lpop('tasks')` to remove it.
* **Design rationale:** There is exactly one worker per GPU. The non-atomic sequence is deliberate: if the GPU fails mid-task and the worker container is restarted, the in-progress task remains at the head of the queue and is automatically reprocessed — no dead-letter queue required. See `README.md` for the single-worker queue model design decision.

## 1.2 Redis Connection Exhaustion (Addressed)
**File:** `utils.py` -> `get_redis_client()`
* **Issue:** `get_redis_client()` instantiates a completely new `redis.StrictRedis` client without utilizing a connection pool. It also executes a `.ping()` for health checking per instantiation.
* **Impact:** `fastapi/app.py` uses `Depends(get_redis)` for every API endpoint. This means every single HTTP request will initiate a new TCP connection to Redis and perform a ping, severely degrading API throughput and potentially exhausting TCP source ports under load (TIME_WAIT states).
* **Recommendation:** Create a single global `ConnectionPool` mapped to a cached `Redis` client instance, and reuse it across requests.

# 2. Web API (FastAPI) Antipatterns

## 2.1 Blocking I/O in Async Endpoints (Rejected: intentional design for EULA compliance)
**File:** `fastapi/app.py`
* **Issue:** `resolve_tasks(pattern)` inside `add_tasks` invokes `yt_dlp`, which makes blocking synchronous HTTP requests to YouTube inside an `async def` endpoint.
* **Design rationale:** The blocking behaviour is intentional. Running `yt_dlp` sequentially ensures all YouTube interactions originate from a single request context, simulating single-user behaviour and avoiding potential EULA violations from concurrent scraping. See `README.md` for the blocking I/O design decision.
* **Remaining concern:** `add_assets` reads the entire file upload into memory before writing it synchronously. This is unrelated to the EULA rationale and could cause memory bloat for large uploads.

# 3. Worker & Subsystem Antipatterns

## 3.1 Unhandled Futures in Azure Transcriber (Intermediate solution — superseded by multi-queue migration)
**File:** `transcriber/azure_transcriber.py` -> `transcribe_audio_file_fire_and_forget()`
* **Issue:** Uses `THREAD_POOL.submit(...)` but ignores the returned `Future` object. Exceptions thrown inside the thread (e.g. Azure API errors, timeouts) are silently swallowed.
* **Context:** The current thread-pool dispatch is an intermediate solution. The planned multi-queue system (see `README.md`) will replace this with proper per-engine queues and failure handling. Once that migration is complete, this pattern will be removed.
* **Until then:** Attaching a `.add_done_callback()` for error logging would reduce silent failure risk.

## 3.2 Polling / Busy Waiting
* **Issue 1:** `azure_transcriber.py` -> `transcribe_audio_file` uses a `while not done: time.sleep(5)` loop to wait for event callbacks. (Accepted)
    * *Recommendation:* Use `threading.Event` and call `event.wait(timeout_seconds)`. This eliminates arbitrary sleep cycles and wakes up immediately upon completion.
* **Issue 2:** `worker.py` -> `yield_task` polls the queue using `time.sleep(poll_interval)`. (Rejected)
    * *Recommendation:* Use Redis blocking operations natively (`BLPOP`).

## 3.3 Expensive Eager File Checks
**File:** `downloaders/utils.py` -> `is_firefox_cookies_available()`
* **Issue:** Uses `Path(...).rglob('cookies.sqlite')` on massive home directories like `~/.mozilla/firefox`.
* **Impact:** This is executed synchronously *every time* `download_video` or `playlist_downloader` is invoked. Traversing the entire Firefox directory structure recursively can be extremely slow and blocking.
* **Recommendation:** Cache the exact cookie path using Python's `functools.lru_cache` after finding it once, or limit the search depth rather than using `rglob`.

## 3.4 Hardcoded Magic String in Core Logic
**File:** `transcriber/whisper_transcriber.py` -> `early_stopper`
* **Issue:** The code hardcodes a suspicious domain-specific string check inside the generalized core transcriber: `if x.text == '请不吝点赞 订阅 转发 打赏支持明镜与点点栏目': return`.
* **Impact:** This is a classic "Leaky Abstraction" / hardcoding antipattern. It forces behavior for a very specific use-case inside a generic transcribe function used by the whole app. 
* **Recommendation:** Remove this immediately. Such logic should be injected via a generic filtering predicate or post-processing hook, rather than hardcoded in the primary transcriber flow.

# 4. General Python Best Practices

* **Overuse of `print` vs `logging`:** Across the entire codebase, `print()` is heavily used for tracking state and errors. Logs lack structured data, log levels (INFO, WARN, ERROR), and timestamps. Switching to the standard `logging` library or `loguru` is highly advised.
* **Swallowed Tracebacks:** Several `try/except Exception as e:` blocks exist (e.g., in `worker.py` or `whisper_transcriber.py`) where only the error message is printed. The traceback is vital for debugging offline workers. Use `logging.exception("...")`.
* **Memory Inefficiencies**: Yielding lazy iterators correctly exists (e.g., in `WhisperSegmentAdaptor`), but `deduplicate_srt_file` explicitly materializes it into memory using `blocks = list(...)` to eagerly close a file handle. It defeats the purpose of the layered generators below it if the file is large, though SRTs are relatively small.
