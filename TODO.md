# TODO — Future Work

Read [AGENTS.md](AGENTS.md) and [README.md](README.md) before accepting an implementation task. This file owns outstanding work, user decisions, and task boundaries. AGENTS owns working policy; the [adversarial review skill](.agents/skills/adversarial-review/SKILL.md) owns the review procedure; README owns current architecture and operating instructions. A document owning product behavior does not exist yet; see NB4.

This file replaces `PLAN.md` and its phase sequence. Dependencies below govern execution. A recorded finding is not permission to combine unrelated changes or redesign the service. Accept a bounded assignment, re-read its code, and implement one independent change per commit. Expand a compact backlog entry into a full boundary before implementing it.

## Maintaining this plan

This section owns how TODO is updated. General working principles belong in AGENTS; the review skill owns the review procedure. Keep this file focused on decisions and work that still matter.

1. Give each finding a stable ID, severity, evidence status, relevant paths, expected outcome, validation criteria, and dependencies. Keep hypotheses distinguishable from validated defects; preserve reviewer classifications and record user dispositions. Do not recycle IDs.
2. Keep unassigned work compact. Before implementation, expand the assigned task into a full boundary: intent, dependencies, implementation direction, non-goals, validation, and done criteria. Link that boundary from the finding instead of duplicating it.
3. Record accepted decisions with their rationale and affected tasks. Keep unresolved choices explicit. When a decision changes, record its supersession and update affected boundaries and dependencies before the implementation commit.
4. Use explicit dependencies and readiness to guide execution. Do not rebuild phase-closure fences or imply that every non-blocking issue must land before unrelated work can proceed.
5. In each implementation commit, remove the completed task's full active entry and execution boundary. Update references, dependencies, legacy mappings, and any affected counts or indexes. Keep at most a concise disposition or governing-document link needed for remaining work or traceability. Put implementation history in the commit and current operations in README.
6. Record deferral or acceptance without change explicitly, with the reason and any revisit trigger. Do not silently drop inherited work or treat a documentation rewrite as an implementation fix.
7. Keep evidence tied to its revision and provenance. Remove obsolete status inventories; historical review results do not certify an executor's current gates. Check local links and ID/dependency consistency after restructuring this file.

## Evidence provenance

The inherited findings come from the 2026-07 full-project review recorded in the former `PLAN.md`. Every one of them was revalidated by source inspection on 2026-09-11 against commit 98c4518, in the project devcontainer on Python 3.12.3. All but the entries below are implemented; the legacy mapping records each disposition.

Gate results at that revision: 197 tests pass, mypy reports no issues across 27 source files, `ruff check .` is clean, and total coverage is 98.5% statement and 92.5% branch. That revision predates the per-file branch coverage work, so its numbers do not describe the current tree.

**Validated** means source inspection or a recorded command at that revision supported the finding. **Not independently validated** identifies work accepted from a user request without separate evidence. Revalidate affected claims and remedies against the execution revision.

### Full-project assessment — 2026-09-12

Reviewed tracked application code, tests, packaging, containers, shell helpers, and documentation at **2f784f2da4b61cf773041f1e90cc5262905c4c06**, in Docker on Python 3.12.3. Three independent assessment agents covered runtime/recovery/API, media/output correctness, and tests/build/operations; the main agent consolidated findings and independently checked the cited source. This was an assessment of existing behavior, not the formal pre-commit review of an application change.

New entries below are **Validated** by source inspection at that revision; entries explicitly naming a reproduction also have bounded empirical evidence. Reproductions used extracted production functions, fake collaborators, installed dependency code, and test-owned temporary files. They covered recovery cursor forwarding, playlist follow-up loss, directory glob matches, suffix-case cleanup, language validation, filename collisions/templates, Azure cleanup, shell input handling, and invalid coverage thresholds. Redis scan semantics were checked against the [XAUTOCLAIM command reference](https://redis.io/docs/latest/commands/xautoclaim/). Temporary artifacts were removed.

The full test suite and application gates were **not run**: B2 and NB12–NB13 identify ownership defects that must be addressed before treating such a run as compliant. No live YouTube, Azure, Redis, model, media-library, or browser-profile checks were performed. Container builds, dependency installation, Python 3.10 execution, and crash durability were not exercised. Installed dependency inspection supports the specific helper/library contracts cited below, not an end-to-end deployment claim. The pre-existing untracked `.devcontainer/devcontainer-lock.json` was excluded and preserved.

**Review boundary:** record all supported findings without an issue-count cap; preserve accepted decisions and inherited IDs; change only this backlog. Findings do not authorize implementation, naming migrations, or new product contracts. Blocking entries identify unsafe validation or substantial loss/wrong-result risks in the existing application; they do not require implementing application fixes in this documentation-only review. Non-blocking entries remain real defects despite lower urgency. Behavior questions were put to the user before their disposition was recorded; the 2026-09-12 decisions below distinguish accepted limitations from requested work. Implementation choices still called out in dependencies remain unselected.

## Decisions and constraints

### Accepted user decisions — 2026-09-11

| ID | Decision | Applies to |
|---|---|---|
| D1 | Tests are not type-checked. The mypy gate covers `youtube_whisperer` only, and widening it is not planned work. | NB3 |
| D2 | The adversarial review harness for Claude Code is the Codex plugin. Antigravity is removed and is not a substitute reviewer; the review skill owns harness dispatch. | Review procedure; B1 closed |
| D3 | Governance files track their ClipboardTTS counterparts. Deviate only for local project context, and record the deviation. | Documentation ownership |
| D4 | `check-coverage.sh` owns the executable coverage policy. `pyproject.toml` keeps the pytest and aggregate coverage configuration. | Coverage policy |

### Decisions carried forward from PLAN.md

| ID | Decision | Applies to |
|---|---|---|
| D5 | The API is unauthenticated and LAN-only by design. README owns the trust model. | legacy finding 25 |
| D6 | `clear_task_queues` snapshots and then deletes non-atomically. Accepted without change and documented as a known limitation. | legacy finding 11 |

These choices do not need to be asked again. Validate exact implementation details against the repository and version-appropriate documentation. Raise a newly discovered material trade-off before changing the boundary; do not reinterpret an accepted decision silently.

### Accepted user decisions — 2026-09-12 review

| ID | Decision and rationale | Applies to |
|---|---|---|
| D7 | Close B1: the user confirms the Claude+Codex review workflow has been proven externally and explicitly requests removal of the blocker. This is user-provided external evidence, not a locally repeated setup or gate run. | B1 disposition |
| D8 | Preserve deduplication that bridges silent gaps between consecutive identical text; that behavior is intentional. | `yield_deduplicated_srt_blocks` |
| D9 | Accept the read-then-delete race for dead letters as well as task queues. A concurrent append may be removed without appearing in the returned snapshot. | `DELETE /dead-letters`; extends D6's accepted limitation |
| D10 | Opening the devcontainer is intended to start the application workers against the configured queue and volumes. | Development startup; automated-test ownership rules still apply |
| D11 | Accept best-effort batch submission: a later enqueue failure may return 500 after earlier tasks were queued, and a client retry can duplicate them. | `POST /tasks` |
| D12 | Manual Redis repair is acceptable for malformed/older persisted payloads; automated quarantine or schema recovery is not requested. | Worker deserialization and queue administration |
| D13 | Support API and worker processes launched from different working directories by resolving filesystem task paths absolutely. | NB22 |
| D14 | Document current configuration behavior: Compose injects `.env`, direct invocations need exported variables, and fresh Compose setup must create the required file. Do not add automatic dotenv loading. | N7, N8 |
| D15 | Empty decoded audio must be reported as a failed task rather than acknowledged without output. | NB23; supersedes the documented successful skip |
| D16 | After successful video download, caption-service errors should allow download-only completion or the requested transcription fallback. | NB24; supersedes fatal caption-service errors for this case |

Accepted limitations above have no implementation assignment. Revisit if the user changes the product contract or evidence shows impact outside the accepted scenario. They do not waive AGENTS' safety requirements.

### Constraints that remain in force

- Preserve the dead-letter contract: a failed transcription reaches `GET /dead-letters` rather than being acknowledged as complete. This is what legacy finding 1 fixed.
- Preserve the XAUTOCLAIM recovery path and the conservative `worker_claim_min_idle_seconds` default that keeps it from stealing live work.
- Preserve README's operating envelope: the filesystem is the source of truth, exactly one `youtube_worker` runs, one `whisper_worker` runs per GPU, and the Whisper model stays resident per process.
- Automated tests never reach YouTube, Azure Speech, a real Redis server, or a real Whisper model. AGENTS owns this rule; do not relax it to make a test simpler.

### Investigation gates

NB2 must inventory the violations an expanded ruff selection produces before choosing the rule set; the entry does not authorize a wholesale reformat. NB3 must establish the true minimum Python version from the syntax and dependencies actually in use before changing `requires-python`. These investigations can expose new decisions; they do not authorize guessing.

## Active backlog

### Blocking

#### B2 — Tests probe filesystem paths outside their ownership

**Severity: High. Validated — source inspection.** [API tests](tests/api/test_app.py):267 call the real directory-listing helper on `/definitely/missing`; [Azure tests](tests/transcriber/test_azure_transcriber.py):169,195,220,247 pass relative `audio.wav`, causing the real transcriber to probe workspace `audio.srt`. An existing file can change the execution path or trigger a prompt. This violates AGENTS even when a probe finds nothing. **Outcome:** all filesystem accesses use test-owned paths and teardown. **Acceptance:** instrument accesses in an isolated test environment, cover existing/missing outputs, and demonstrate no access outside owned temporary paths. **Dependencies:** resolve before running baseline gates; coordinate configuration ownership with NB12. No production files may be seeded or copied to prove non-access.

#### B3 — A later playlist failure loses earlier transcription follow-ups

**Severity: High. Validated — source and isolated reproduction.** [YouTubeWorker.process_task](youtube_whisperer/workers/youtube_worker.py):53–66 buffers follow-ups until the entire playlist/channel finishes. A first successful download without SRT followed by a second download exception produces zero enqueue calls; the parent then dead-letters and is acknowledged. Earlier media remains without its requested transcription. **Outcome:** preserve and deliver completed-item progress despite later expansion/download failure. **Acceptance:** earlier success followed by extraction/download failure, failed enqueue, retry, and restart do not strand required follow-ups. **Dependencies:** decide stop-versus-continue behavior for remaining playlist items before implementation; recording the defect does not choose that policy.

#### B4 — URL translation can finish with source-language captions

**Severity: High. Validated — source and synthetic language lookup.** [Download orchestration](youtube_whisperer/downloaders/__init__.py):27 passes language but no mode to the transcript downloader; [language matching](youtube_whisperer/downloaders/transcript_downloader.py):70 uses the source language, and [YouTubeWorker](youtube_whisperer/workers/youtube_worker.py):56–62 treats a found transcript as completion. For `zh->en` translate work, available Chinese captions suppress Whisper and produce Chinese output. **Outcome:** source-language captions cannot satisfy an English translation request. **Acceptance:** source-caption, target-caption, missing-caption, and invalid-target cases preserve requested translation semantics. **Dependencies:** choose target-caption reuse versus Whisper preference before implementation; preserve README's separate, documented Azure-mode limitation.

#### B5 — Title-only filenames silently alias different videos

**Severity: High. Validated — source and isolated equal-title reproduction.** [Video naming](youtube_whisperer/downloaders/video_downloader.py):55–58 and [transcript naming](youtube_whisperer/downloaders/transcript_downloader.py):186–187 derive identity solely from sanitized/truncated titles. Distinct video IDs can share MP4/SRT paths. Under worker `NEVER` semantics, the second video reuses the first media; if the first SRT is absent, captions can be paired with the wrong video. **Outcome:** preserve distinct video identities and safe repeat processing of the same video. **Acceptance:** equal titles, sanitization collisions, truncation collisions, and repeat downloads cannot substitute unrelated content. **Dependencies:** user naming/migration decision before implementation; preserve the human-browsable media-library contract and coordinate NB8.

#### B6 — Partial SRT writes are accepted as completed transcription on retry

**Severity: High. Validated — source inspection; no process-crash test.** [SRT serialization](youtube_whisperer/adaptors/srt_deduplicator.py):162,186 and [caption saving](youtube_whisperer/downloaders/transcript_downloader.py):172 write directly to final files. A crash or I/O failure after truncation can leave a partial SRT; both transcribers and the downloader treat any existing SRT as complete under `NEVER`. **Outcome:** only completed output becomes visible as the completion marker, with prior valid output preserved on failure. **Acceptance:** injected mid-write failure and interruption leave no false completion marker; retry produces complete output, and overwrite policies remain intact. **Dependencies:** coordinate publication semantics with NB10 and B7, but keep independently implementable artifact changes separate. The helper creates parents only: lazy Whisper rejection before `write_text` does not itself create a partial SRT.

#### B7 — Failed WAV conversion leaves a sidecar that Azure blindly reuses

**Severity: High. Validated — source inspection.** [WAV conversion](youtube_whisperer/transcriber/waveform_loader.py):65–76 writes the final WAV directly, while [AzureWorker](youtube_whisperer/workers/azure_worker.py):43–49 checks only whether that file exists. Interrupted/failed ffmpeg conversion can leave a truncated sidecar; a retry reuses it, causing repeated failures or transcription of only a prefix. **Outcome:** publish/reuse completed conversions and clean only owned incomplete artifacts. **Acceptance:** failure after partial WAV creation followed by retry regenerates the correct input; existing good WAVs remain reusable and untouched when conversion fails. **Dependencies:** align the completion invariant with B6 without introducing an unsolicited metadata store.

### Non-blocking

#### NB2 — Ruff runs with its default rule set

**Validated — no `[tool.ruff]` configuration exists at 98c4518.** Only the default `E4`, `E7`, `E9`, and `F` rules are active, so nothing enforces line length, import ordering, docstring style, or common-bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing currently produces one. **Paths:** [pyproject.toml](pyproject.toml). **Direction:** after the inventory required by the investigation gate, select a broader set. Pydocstyle with the Google convention would mechanize the docstring rule that AGENTS states in prose. **Acceptance:** `ruff check .` passes under the expanded selection and every `noqa` carries the rationale AGENTS requires. **Non-goals:** restructuring code beyond what the selected rules demand. **Current inventory — 2026-09-12:** source still uses `Any` in language-schema hooks, playlist metadata, Azure callbacks, and model parameters; several source classes lack docstrings. Tests also retain string-based patches (for example `tests/transcriber/test_model_parameters.py:7`) and alternate import forms. Inventory these separately from runtime defects, and distinguish rules Ruff can enforce from typing or test-structure work; do not claim broader lint selection alone resolves them.

#### NB3 — The declared Python floor is incompatible with the source

**Validated — source inspection at 2f784f2 on 2026-09-12.** `requires-python = ">=3.10"`, but [lang_code_adaptor.py](youtube_whisperer/adaptors/lang_code_adaptor.py) imports `Self` from `typing` at line 3; that symbol was introduced in Python 3.11. The task models and API/worker import chains therefore fail on the declared 3.10 floor. This is stronger evidence than the inherited unverified-support finding; no Python 3.10 run was performed. The devcontainer runs 3.12.3, and no environment in the repository exercises 3.10 or 3.11. The repository has no continuous integration at all, so the gates run only where an agent or the user runs them. **Paths:** [pyproject.toml](pyproject.toml), [Dockerfile](Dockerfile), [.devcontainer/](.devcontainer/). **Direction:** determine the real minimum from the code and dependencies, then either correct `requires-python` or verify the floor with a GitHub Actions matrix running the three gates across the supported versions. **Acceptance:** the declared floor is either verified by a matrix run or corrected to what is actually supported. Note D1: any CI job runs mypy against the package only.

#### NB4 — Product behavior has no owning document

**Not independently validated — user request, 2026-09-11.** README carries user-visible behavior implicitly alongside architecture, so there is no document that owns the product contract, and AGENTS' Document Boundaries has no entry for one. **Paths:** new `USER_STORIES.md`, [README.md](README.md), [AGENTS.md](AGENTS.md). **Direction:** capture the user-visible contract, including task submission and resolution, the queue and dead-letter endpoints, asset listing and cleanup, the language whitelist and rejection policy, and SRT as the delivered output. Link it from Document Boundaries and stop duplicating it in README. **Acceptance:** USER_STORIES owns product behavior and the other documents link rather than restate it.

#### NB5 — Lock-file regeneration is a side effect of creating the container

**Validated — [postCreateCommand.sh](.devcontainer/postCreateCommand.sh) at 98c4518.** Inherited from legacy finding 26. `pip freeze` rewrites `requirements.txt` on every devcontainer create, so the lock file changes on a plain rebuild rather than when dependencies actually change; the repeated "Updated dependencies" commits come from this. README now documents the behavior as it is. **Direction:** make regeneration deliberate. PLAN.md proposed an `update_lock.sh`, that script was never added, and the user has since said it is not the intended route, so the mechanism is an open question for the user. **Acceptance:** opening the devcontainer no longer modifies `requirements.txt`, and README documents how the lock file is refreshed instead.

#### NB6 — Orphan recovery discards the XAUTOCLAIM scan cursor

**Severity: Medium. Validated — source, installed redis-py signature, isolated cursor replay, and Redis command reference.** [yield_task](youtube_whisperer/workers/common.py):84–86 always starts at default `0-0` and discards the next cursor. With `COUNT=1`, Redis scans at most ten entries: an ineligible prefix can hide eligible later entries until that prefix changes. **Outcome:** progress through the full pending list without lowering the accepted idle threshold or starving new work. **Acceptance:** ineligible prefix, eligible later entry, empty scan pages, cursor wrap, and continued new-work polling. **Dependencies:** preserve the six-hour policy and coordinate NB7.

#### NB7 — Invalid polling configuration can stop eventual recovery

**Severity: Medium. Validated — source inspection.** [CLI parsing](youtube_whisperer/workers/__main__.py):97 accepts zero; [yield_task](youtube_whisperer/workers/common.py):107 turns it into `BLOCK 0`, an infinite read. If an orphan becomes eligible after the initial recovery pass and no new messages arrive, recovery never runs again. Negative polling/claim intervals also reach Redis without application validation. **Outcome:** enforce timing values consistent with finite recovery passes. **Acceptance:** invalid values fail before Redis interaction; positive values and the default threshold remain unchanged. **Dependencies:** NB6 shares the recovery invariant. Any intentional infinite-wait mode requires a separate decision.

#### NB8 — Video titles are interpreted as yt-dlp template expressions

**Severity: Medium. Validated — installed yt-dlp `prepare_filename` with synthetic metadata.** [download_video](youtube_whisperer/downloaders/video_downloader.py):33 supplies a literal path as `outtmpl`. Title `Progress %(id)s` survives sanitization, but yt-dlp expands it to `Progress AAAAAAAAAAA.mp4` while the wrapper returns `Progress %(id)s.mp4`. Follow-up work and captions use the wrong path. **Outcome:** returned media paths and caption stems match actual output even with template metacharacters. **Acceptance:** literal `%` and `%(id)s` titles, ordinary titles, and directory components resolve consistently without network calls. **Dependencies:** coordinate B5's naming decision; this escaping defect is independently reproducible.

#### NB9 — Azure duration-inspection failure leaks a started recognizer

**Severity: Medium. Validated — source and fake-recognizer reproduction (`started=1`, `stopped=0`).** [transcribe_audio_file](youtube_whisperer/transcriber/azure_transcriber.py):108–116 starts recognition, then inspects duration before entering its cleanup `try/finally`. An `sf.info` failure skips stop. **Outcome:** every started session is stopped on failure, with no output and normal worker error propagation. **Acceptance:** duration-inspection failure, startup failure, timeout, cancellation, and success have explicit owned cleanup. **Dependencies:** none; tests must meet B2/NB12/NB13 ownership requirements.

#### NB10 — Azure final saving drops the caller's overwrite policy

**Severity: Medium. Validated — source inspection.** [Azure saving](youtube_whisperer/transcriber/azure_transcriber.py):121 omits `overwrite`, so the serializer defaults to `PROMPT`. `ALWAYS` can prompt again; an SRT appearing during recognition can prompt or raise EOF even though the worker supplied `NEVER`. **Outcome:** honor the caller's policy throughout final publication. **Acceptance:** allowed replacement, denied replacement, and a competing output appearing during recognition never read stdin in worker mode. **Dependencies:** coordinate B6; update the existing test that currently expects only `deduplicate=True`.

#### NB11 — Allowed video overwrites are not forwarded to yt-dlp

**Severity: Medium. Validated — source and installed yt-dlp existing-file behavior.** [download_video](youtube_whisperer/downloaders/video_downloader.py):28–40 checks overwrite permission but never configures yt-dlp to overwrite. The pathlib helper only returns permission; yt-dlp's existing-video path defaults to retaining the file. Consequently `ALWAYS` does not fulfill the wrapper's replacement contract. **Outcome:** replace existing videos only when authorized by the supplied policy. **Acceptance:** owned existing-file scenarios verify `ALWAYS` replaces and `NEVER` preserves, using the library contract without external downloads. **Dependencies:** none; mocking the entire download operation is insufficient verification.

#### NB12 — Tests rely on ambient settings and production-global clients

**Severity: Medium. Validated — source inspection.** [Utility tests](tests/test_utils.py):20 assert defaults on the import-created real Redis pool; [API tests](tests/api/test_app.py):41,46 inspect production globals; [Azure tests](tests/transcriber/test_azure_transcriber.py):155–247 invoke real `Settings`, potentially passing ambient credentials into doubles; [model-parameter tests](tests/transcriber/test_model_parameters.py):38 compare against the configured model-cache path. **Outcome:** own settings, synthetic credentials, filesystem paths, and clients per test, with teardown. **Acceptance:** isolated synthetic environment variations do not alter expected behavior or touch real configuration, services, or cache paths. **Dependencies:** B2; establish this isolation before claiming compliant baseline evidence.

#### NB13 — Azure test callbacks have no guaranteed quiescence

**Severity: Medium. Validated — source inspection.** [FakeSpeechRecognizer](tests/transcriber/test_azure_transcriber.py):44 launches an untracked daemon thread; its stop method only increments a counter. Failures/timeouts can leave callbacks running after the test, with no cancellation, join, or local late-error accounting. The timeout test at line 183 also relies on a real 0.01-second wait. **Outcome:** test-owned asynchronous lifecycle and deterministic completion on both success and failure. **Acceptance:** injected callback failure, delayed callback, timeout, and assertion failure leave no thread or late mutation; use controlled completion instead of elapsed-time sleeps. **Dependencies:** B2/NB12; independent of runtime NB9.

#### NB14 — A failed cache test leaves its fake model resident

**Severity: Low. Validated — source inspection.** [Whisper cache test](tests/transcriber/test_whisper_transcriber.py):91–103 clears the cache after assertions without a finalizer. An assertion failure leaves the mocked model cached after patches are restored, contaminating later randomly ordered tests. **Outcome:** own and clear the cache on every exit. **Acceptance:** inject failure after cache population and verify teardown and a subsequent test observe no stale fake. **Dependencies:** none; do not load a real model to test this.

#### NB15 — API handlers block the event loop with synchronous work

**Severity: Medium. Validated — source inspection.** [API endpoints](youtube_whisperer/api/app.py):77–240 are `async def` but call synchronous Redis/glob/directory/deletion operations directly. Slow Redis or a large traversal stalls unrelated requests in the configured single-process uvicorn service; the shared Redis pool deliberately has no read timeout for workers. **Outcome:** preserve responsiveness while blocking dependencies wait. **Acceptance:** hold one dependency behind an explicit barrier and verify an independent request completes; release and quiesce all work. **Dependencies:** preserve worker blocking-read semantics; do not impose a short shared socket timeout as a mechanical fix.

#### NB16 — Filesystem glob resolution queues directories as files

**Severity: Medium. Validated — source and owned-directory reproduction.** [resolve_filesystem_tasks](youtube_whisperer/api/app.py):97 turns every glob match into a task without checking file type. Mixed or directory-only patterns report directories as successful submissions and send them to transcription. **Outcome:** enqueue file candidates while preserving unmatched-pattern reporting. **Acceptance:** regular file, directory, mixed, and directory-only fixtures; no host filesystem access. **Dependencies:** none. This finding does not authorize an extension whitelist or restrict the accepted arbitrary-glob trust model.

#### NB17 — Non-string language input escapes validation as TypeError

**Severity: Medium. Validated — isolated Pydantic TypeAdapter reproduction and API exception-path inspection.** [LanguageCode deserialization](youtube_whisperer/adaptors/lang_code_adaptor.py):112 raises `TypeError` for numeric, null, or collection input. Current Pydantic propagates that error instead of turning it into validation failure; the API's general handler therefore produces 500 for malformed client input. The same reproduction gives `ValidationError` for unsupported string `fr`. **Outcome:** invalid language types produce the normal client-validation response. **Acceptance:** numeric/null/list/object inputs return 422 without enqueueing; registered strings and LanguageCode instances remain accepted. **Dependencies:** none; preserve the language whitelist.

#### NB18 — Supported YouTube URL forms fail transcript ID extraction

**Severity: Medium. Validated — pure parser reproductions and installed yt-dlp support inspection.** [get_video_id](youtube_whisperer/downloaders/transcript_downloader.py):48–56 rejects bare `youtube.com`, `m.youtube.com`, and `/shorts/` URLs. [Single-video extraction](youtube_whisperer/downloaders/playlist_downloader.py):58–62 preserves the original URL, so media download can succeed before caption routing fails and dead-letters the task, including download-only work. **Outcome:** supported video URLs resolve consistently across download and transcript stages. **Acceptance:** bare/mobile/shorts/watch/live/short-link cases and malformed input use fake metadata and no service calls. **Dependencies:** none; do not expand this into arbitrary-site support.

#### NB19 — Transcript HTTP operations have no timeout

**Severity: Medium. Validated — source and installed `youtube-transcript-api==1.2.4` inspection.** [Transcript listing/fetching](youtube_whisperer/downloaders/transcript_downloader.py):92,114 use the default client. Its ordinary requests session performs GET/POST without timeouts; the application supplies neither a bounded client nor an execution deadline. A stalled response can occupy the required single YouTube worker indefinitely. **Outcome:** bound stalled caption operations. **Acceptance:** a controlled stalled HTTP double reaches a bounded, observable completion/failure and releases the worker without real YouTube access. **Dependencies:** apply D16/NB24 after successful media download; select an appropriate finite timeout before implementation. Adding a timeout does not authorize scaling the YouTube worker.

#### NB20 — Invalid coverage thresholds disable per-file comparisons

**Severity: Low. Validated — extracted coverage parser with synthetic reports.** [check-coverage.sh](check-coverage.sh):33 accepts non-finite and out-of-range floats. A 1% report fails with `80` but reports success with `nan` or `-1`. The full script still has pytest's aggregate guard; the defect bypasses the separate per-file/branch checks when aggregate coverage passes. **Outcome:** reject invalid thresholds before running pytest. **Acceptance:** NaN, infinities, negative values and values above 100 fail clearly; valid boundaries and ordinary thresholds behave as documented. **Dependencies:** preserve D4 and the existing gate policy.

#### NB21 — Subtitle text extraction deletes valid dialogue and mishandles CRLF

**Severity: Medium. Validated — synthetic SRT shell reproductions.** [extract_subtitle_text.sh](extract_subtitle_text.sh):13 removes every numeric line, so dialogue such as `2026` disappears with cue indexes. On CRLF input, numeric indexes and blank lines survive because the regular expressions encounter carriage returns. **Outcome:** distinguish SRT structure from cue content and handle both line endings. **Acceptance:** numeric/ordinary dialogue, timestamps, indexes, blank lines, and equivalent LF/CRLF files produce the intended text. **Dependencies:** none; protect both defects in one cohesive parser boundary.

#### NB22 — Relative task paths change meaning in a worker's working directory

**Severity: Medium. Validated — source inspection; requested under D13.** [Filesystem resolution](youtube_whisperer/api/app.py):97 retains relative glob results; [TranscriptionWorker](youtube_whisperer/workers/common.py):245 interprets them with `Path(task.source)` in the worker process. API and worker launches from different directories therefore target different files or fail despite successful resolution. Compose currently shares its working directory, so that deployment masks the defect. **Outcome:** enqueue absolute paths to the actual API-resolved files. **Acceptance:** API resolution in one owned directory followed by worker processing in another uses the same intended file; absolute sources, whitespace handling, and metadata are preserved. **Dependencies:** D13; coordinate file filtering with NB16 without introducing a new path-access restriction.

#### NB23 — Empty Whisper input is acknowledged without output or a dead letter

**Severity: Medium. Validated — source inspection; changed product disposition under D15.** [Whisper transcription](youtube_whisperer/transcriber/whisper_transcriber.py):127–129 returns `None` for an empty waveform; [WhisperWorker](youtube_whisperer/workers/whisper_worker.py):88 ignores the return, so the common loop acknowledges success with no SRT. **Outcome:** empty decoded audio raises an actionable failure that reaches the dead-letter endpoint. **Acceptance:** controlled empty waveform produces no SRT and one durable failure before acknowledgement; nonempty success and existing-output behavior remain covered. **Dependencies:** D15 supersedes the current documented skip; update that docstring and the test that expects `None` in the implementation commit.

#### NB24 — Caption-service errors abort already-downloaded video work

**Severity: Medium. Validated — source inspection; requested under D16.** [Transcript lookup](youtube_whisperer/downloaders/transcript_downloader.py):89–117 handles disabled/missing transcripts but propagates other service failures through [download orchestration](youtube_whisperer/downloaders/__init__.py):26–28. After media has downloaded, the worker therefore dead-letters download-only work or skips its requested transcription fallback. **Outcome:** retain the successful media result, report the caption-service problem, and complete download-only work or enqueue the selected transcriber. **Acceptance:** listing/fetching service errors after successful download preserve the media and chosen fallback; genuine media-download, local output-write, and transcription failures still surface appropriately. **Dependencies:** D16; coordinate NB19 timeout handling, B3 playlist progress, and B4 translation semantics. Do not catch all local/programming errors as though captions were merely unavailable.

### Nits

#### N1 — Asset cleanup reconstructs the wrong case-sensitive paths

**Severity: Low. Validated — source and owned-file reproduction.** [Suffix mapping/selection](youtube_whisperer/api/app.py):202,223 lowercases suffixes and reconstructs paths. On Linux, `video.mp4` + `video.srt` + `video.WAV` selects nonexistent `video.wav`, leaving the redundant WAV. **Outcome:** retain actual paths while matching suffixes case-insensitively. **Acceptance:** mixed-case extensions and coexisting case variants clean correctly, preserving MP4/SRT. **Dependencies:** none.

#### N2 — Empty media directories produce a fictitious filename

**Severity: Low. Validated — owned empty-directory shell reproduction.** [ls_mp4_without_srt.sh](ls_mp4_without_srt.sh):19 iterates an unmatched glob literally and prints `<directory>/*.mp4` with exit 0. **Outcome:** report only existing MP4 files missing SRT. **Acceptance:** empty directory produces no paths; missing/present SRT and filenames with spaces remain correct. **Dependencies:** none.

#### N3 — Standalone build instructions use a different helper revision

**Severity: Low. Validated — source comparison.** [README](README.md):158 and its configuration table use `v1.0.0`, while [CPU Compose](docker-compose.cpu.yaml):7 uses `v1.1.0`. Following the standalone build example therefore selects different helpers. **Outcome:** current instructions agree with the configured revision. **Acceptance:** inspect all helper-version references and local links. **Dependencies:** none; this correction needs no image build or application gates.

#### N4 — Waveform documentation incorrectly claims streaming memory use

**Severity: Low. Validated — source inspection.** [load_whisper_waveform_from_file](youtube_whisperer/transcriber/waveform_loader.py):22 says raw bytes never reside in Python, but lines 42–46 capture the entire PCM byte string and create additional arrays. **Outcome:** describe actual buffering and ownership. **Acceptance:** docstring matches the capture/conversion path. **Dependencies:** none; a streaming or memory-optimization redesign needs a separate assignment and measurements.

#### N5 — Filename-limit documentation uses characters instead of bytes

**Severity: Low. Validated — pinned pathlib-extensions implementation inspection.** [README](README.md):135 says filenames truncate to 220 characters; the helper measures UTF-8 bytes, so multibyte titles have fewer characters. **Outcome:** state the real unit. **Acceptance:** compare ASCII and multibyte examples with the pinned helper without media access. **Dependencies:** coordinate B5 if its naming policy changes.

#### N6 — Source docstrings retain obsolete worker and failure contracts

**Severity: Low. Validated — source inspection.** [Worker entry point](youtube_whisperer/workers/__main__.py):48–58 describes slot-specific active queues and limits slot routing to Whisper/Azure, although all roles use Redis streams and the resolved consumer name. [Azure transcriber](youtube_whisperer/transcriber/azure_transcriber.py):70 says failures return `None`, although its handled failures raise. **Outcome:** describe current consumer identity and failure propagation. **Acceptance:** compare docstrings/CLI help with role dispatch and error branches. **Dependencies:** none; preserve runtime behavior.

#### N7 — Direct-run documentation incorrectly promises dotenv loading

**Severity: Low. Validated — source comparison; documentation-only disposition under D14.** [README configuration](README.md):167 says settings read environment variables and `.env`; [Settings](youtube_whisperer/config.py):7 configures no dotenv source. Compose injects the file, but the documented direct API/worker commands do not. **Outcome:** describe exported environment variables for direct launches and Compose's separate injection behavior. **Acceptance:** configuration prose and direct-run examples agree with the actual settings source; no real `.env` is inspected. **Dependencies:** D14; do not implement automatic dotenv loading.

#### N8 — Fresh Compose instructions omit creation of its mandatory env file

**Severity: Low. Validated — tracked Compose/documentation inspection; documentation-only disposition under D14.** [CPU Compose](docker-compose.cpu.yaml):33,50,64,78 requires `.env` for every application service. README presents `compose up` without a file-creation step although the ignored file is absent from a fresh checkout. **Outcome:** document creating the required empty/configured file and when Azure credentials are needed. **Acceptance:** setup is complete for a clean checkout and distinguishes file presence from optional credential values; validate only with synthetic configuration and no service startup or secrets. **Dependencies:** D14 and N7; preserve current Compose behavior.

## Ready for implementation

NB4 is ready as written. NB2 and NB3 need their investigation gates cleared first. NB5 needs a user decision on the mechanism before it has a boundary.

B2 and NB12–NB13 establish the safe test environment required for subsequent application gates. Other new entries are compact findings, not implementation assignments: expand each boundary first and honor its explicit product-policy dependencies. Naming, translation-caption preference, and playlist continuation must be settled before their dependent implementation. D13–D16 settle the product outcomes for NB22–NB24 and N7–N8; their implementation boundaries still need expansion. Documentation nits can proceed independently under AGENTS' documentation-only exemption.

## Deferred, accepted, and completed dispositions

- B1 is closed at the user's explicit direction on 2026-09-12: the Claude+Codex workflow was proven externally (D7). No remaining setup blocker is carried forward.
- The 2026-09-12 review accepts gap-bridging deduplication, dead-letter clearing races, production-worker startup in the devcontainer, best-effort batch enqueue, and manual repair of malformed Redis payloads under D8–D12; these are not omitted defects awaiting an implicit fix.

- Legacy finding 2, path traversal in `POST /assets`, is obsolete rather than fixed: the upload endpoint no longer exists, so no client-controlled filename reaches the filesystem. Revisit only if uploads return.
- Legacy finding 11 is accepted without change under D6 and documented in README's known limitations.
- Legacy finding 25 is accepted under D5; README's security and trust model section owns it.
- Legacy finding 9 is closed. The single remaining `assert` narrows a type and carries a comment saying so; it does not validate external input.
- NB1 is implemented. The three files below the branch-coverage threshold are covered and `./check-coverage.sh` passes at the default threshold; the implementation commit holds the evidence.
- Legacy finding 26 remains open as NB5. Every other inherited finding is implemented.
- `ISSUES.md` was deleted before the PLAN.md review; its still-open item became legacy finding 5 and is implemented.

### Legacy finding mapping

PLAN.md numbering is preserved for traceability. Disposition verified 2026-09-11 at 98c4518.

| Legacy finding | Disposition |
|---|---|
| 1, 14 | Implemented; the transcriber raises and the worker calls it directly, so failures dead-letter |
| 2 | Obsolete; the upload endpoint was removed |
| 3 | Implemented; packaging includes only `youtube_whisperer*` |
| 4 | Implemented; `Task.source` is required |
| 5 | Implemented; per-replica consumer names plus an XAUTOCLAIM recovery pass |
| 6 | Implemented; flat extraction branches on `entries` and skips unusable ones |
| 7 | Implemented; the Azure timeout has a documented floor |
| 8 | Implemented; `Settings.redis_host` replaces the hardcoded host |
| 9 | Implemented; the remaining assert narrows a type only |
| 10 | Implemented; the unreachable branch is gone |
| 11 | Accepted without change; see D6 |
| 12, 13 | Implemented; domain models live in `models.py` and the web layer is `api/` |
| 15 | Implemented; the Whisper model is cached per process |
| 16 | Implemented; the package logs and no longer prints |
| 17, 18 | Implemented; the legacy repr parser and the dead helpers are removed |
| 19 | Implemented; the test layout mirrors the package |
| 20, 22, 23, 24 | Implemented; pinned Redis image, cache-friendly Dockerfile order, corrected ignore glob, healthcheck |
| 21 | Implemented; host paths and proxies are environment-driven |
| 25 | Accepted; see D5 |
| 26 | Open; see NB5 |
| 27 | Implemented; README was rewritten and documents the previously undocumented choices |

## Integration acceptance

Review integrated changes against the accepted decisions and the current README. Do not require every non-blocking task to land before unrelated work proceeds; record explicit defer or accept dispositions and their reasons.

AGENTS owns the required gates and the review obligation. Supplement them with checks that match what changed: queue and dead-letter behavior for worker changes, extraction behavior for downloader changes, and an end-to-end compose smoke run for infrastructure changes. Clean static analysis is not proof of correct concurrent behavior.

Keep live-service checks out of the automated suite. Exercising YouTube or Azure Speech needs explicit authorization and credentials, and must record no keys or personal media paths. Record evidence at its actual revision. Remove a completed entry in its implementation commit, keeping only the concise disposition that remaining work or traceability needs.
