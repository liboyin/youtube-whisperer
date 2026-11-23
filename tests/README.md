# Writing tests

[AGENTS.md](../AGENTS.md#tests) owns the testing rules. This file owns the conventions that apply them. [README Testing](../README.md#testing) owns how the suite and the gates run.

## Layout and naming

- Tests mirror the package: `tests/<subpackage>/test_<module>.py` tests `youtube_whisperer/<subpackage>/<module>.py`.
- Tests of standalone scripts outside the package live under `tests/tooling/`. The shell tools and the references of the review skill are such scripts.
- Import the module under test as `import youtube_whisperer.my_module as testee`. Call it as `testee.function_name`, and patch its attributes with `patch.object(testee, 'attribute', ...)`.
- A standalone script MAY be loaded by file path as `testee`, with the same conventions.
- Order the test functions to match the order of the functions in the source file.
- A test name describes the protected behavior. Each test keeps a one-line docstring.
- Comments explain non-obvious reasons or trade-offs.

Shared fixtures live in `conftest.py` files:

- `tests/conftest.py` owns the bootstrap that the next section describes, and the fixtures `owned_path_probes` and `caption_http`.
- `tests/downloaders/conftest.py` holds the `FakeYoutubeDL` double.
- `tests/tooling/conftest.py` builds the owned subprocess environment for the tests of shell tools.

## The bootstrap

`tests/conftest.py` isolates the application's settings before any test module imports them.

- It refuses to run if `youtube_whisperer.config` or `youtube_whisperer.utils` was imported before it. Start pytest in a fresh Python process. A repeated embedded `pytest.main()` is refused too.
- It points `HOME`, the media library and the model directory at a temporary directory that the session owns.
- It sets synthetic values for the other settings, such as the Redis host `queue.test.invalid` and the model name `test-model`.
- It removes the Azure Speech credentials and the host-path variables `ASSETS_DIR`, `FIREFOX_PROFILE_DIR` and `WHISPER_MODELS_VOLUME`.
- At the end of the session, it restores the inherited environment and removes its directory.

## Owned state

- Use test-owned state for filesystem paths, environment variables, settings and service clients.
- Prefer fixtures that own their teardown, such as `tmp_path` and `monkeypatch`.
- Snapshot and restore only the state that the test owns.
- Do not seed real configuration to prove that the code does not access it.
- Leave no files, environment variables or streams behind.
- If the code under test probes paths, wrap the operation in `owned_path_probes()`. The fixture fails the test for a probe outside its `tmp_path`.

## External services

The suite has no network guard. Each test replaces every external service with a double:

- **Redis:** a mocked client. No test opens a connection to a server.
- **YouTube:** `FakeYoutubeDL` for downloads, and the `caption_http` fixture for captions. That fixture mounts a scripted transport adapter on every caption session, so no request reaches a socket.
- **Azure Speech:** the fake Speech SDK in `tests/transcriber/test_azure_transcriber.py`, or patched `speechsdk` attributes.
- **Whisper:** a patched `WhisperModel` constructor that returns a mock. No test loads real weights.

These rules apply to the doubles:

- A double that the code under test could bypass is not isolation. Patch the module attribute that the code calls.
- If a test needs a destination that must reach nothing, use a reserved one: `192.0.2.1` (RFC 5737) or a name under `.invalid` (RFC 2606). These reach nothing even under a mutant that bypasses the double.

## Asynchronous work

- Background work that a test starts, directly or through the code under test, must be stopped and joined before the test ends. Use a `finally`, and assert that the work is not alive.
- A shared asynchronous resource or a process-global double needs five things: ownership by one test, synchronized access, cancellation, quiescence, and local accounting for late work.
- These guarantees hold after timeouts and failures too. A completion signal alone does not prove that callbacks or background work have stopped.

## Time

- If only time can falsify a property, a bounded wall-time assertion is permitted. A thread-safe wake-up and a capped wait are examples.
- Bound the assertion well below the duration that the defect would cause, and explain the bound in a comment.
- Pair the assertion with explicit completion signals wherever they exist.
- An injected clock must never drive a deadline that the code waits out on a real clock, as asyncio's waits do. A clock that does not advance in real time makes that wait endless.

## Coverage

- An exclusion from coverage needs a narrow rationale and an end-to-end smoke check. Validate the check whenever the exclusion changes.
- The location of a directory alone does not justify the exclusion of application logic.
- Record each manual check that was not performed as a limitation.
