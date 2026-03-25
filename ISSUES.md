This document is intended for AI agents to document issues and antipatterns found during code reviews. Note that not all of them are genuine issues - some might be design choices.

# 1. Critical Concurrency & Architecture Flaws

## 1.1 Non-Atomic Queue Processing in Worker (Rejcted: local transcriber works asynchronously because there is only one GPU. Azure transcribers are dispatched in a thread pool. See Future Work section in README.md)
**File:** `worker.py` -> `process_queue()` and `yield_task()`
* **Issue:** The worker uses `lrange('tasks', 0, 0)` to read a task, processes it (which could take minutes), and then calls `lpop('tasks')` to remove it.
* **Impact:** In a multi-worker setup, both workers will read the exact same task from `lrange` and process it redundantly. When they finish, they both execute `lpop`. If one worker finishes first, it pops the task. When the second finishes, it pops the *next* task in the queue, completely dropping a task without processing it!
* **Recommendation:** The architectural document (AGENTS.md) specifies using `BRPOPLPUSH` for atomic consumption. The code does not reflect this. It should use `BLPOP` or `BRPOPLPUSH` to atomically grab tasks and maintain a processing queue.

## 1.2 Redis Connection Exhaustion (Addressed)
**File:** `utils.py` -> `get_redis_client()`
* **Issue:** `get_redis_client()` instantiates a completely new `redis.StrictRedis` client without utilizing a connection pool. It also executes a `.ping()` for health checking per instantiation.
* **Impact:** `fastapi/app.py` uses `Depends(get_redis)` for every API endpoint. This means every single HTTP request will initiate a new TCP connection to Redis and perform a ping, severely degrading API throughput and potentially exhausting TCP source ports under load (TIME_WAIT states).
* **Recommendation:** Create a single global `ConnectionPool` mapped to a cached `Redis` client instance, and reuse it across requests.

# 2. Web API (FastAPI) Antipatterns

## 2.1 Blocking I/O in Async Endpoints
**File:** `fastapi/app.py`
* **Issue:** You have several async endpoints executing synchronous blocking functions:
    * `resolve_tasks(pattern)` inside `add_tasks`: It eventually invokes `yt_dlp` which makes heavy, blocking synchronous HTTP requests to YouTube.
    * `add_assets`: Reads the whole file upload into memory (`await upload.read()`) then writes it via synchronous I/O (`with target_path.open("wb") as f: f.write(...)`). Uploading a 2GB file will cause extreme memory bloat and block the event loop while saving to disk.
* **Impact:** Because these endpoints are defined as `async def`, any blocking call halts the *entire* FastAPI event loop. Other requests won't be served while `yt_dlp` is fetching information or a file is saving.
* **Recommendation:** 
    * Use thread pools for blocking functions: `await anyio.to_thread.run_sync(resolve_tasks, ...)`.
    * For file uploads, use `shutil.copyfileobj` in a thread, or async filesystem operations. Avoid reading the entire file contents into RAM.

# 3. Worker & Subsystem Antipatterns

## 3.1 Silent Threat: Unhandled Futures (Addressed)
**File:** `transcriber/azure_transcriber.py` -> `transcribe_audio_file_fire_and_forget()`
* **Issue:** Uses `THREAD_POOL.submit(...)` but ignores the returned `Future` object.
* **Impact:** If `transcribe_audio_file` throws an exception (e.g., Azure API error or timeout), the exception gets swallowed completely and silently because the future is never awaited or a callback is never attached (`.add_done_callback()`).
* **Recommendation:** Attach an error-checking callback to the future to at least log failures, or better, implement proper dead-letter queue behavior as per the architecture spec.

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
