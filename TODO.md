# TODO — Future Work

Read [AGENTS.md](AGENTS.md), [DESIGN.md](DESIGN.md) and the relevant [README](README.md) operating instructions before accepting an implementation task. This file owns outstanding work, unresolved choices and task boundaries. DESIGN owns system design, product contracts and accepted user decisions; AGENTS and the [adversarial review skill](.agents/skills/adversarial-review/SKILL.md) own working policy and review.

This file replaces `PLAN.md` and its phase sequence. Dependencies below govern execution. A recorded finding is not permission to combine unrelated changes or redesign the service. Accept a bounded assignment, re-read its code, and implement one independent change per commit. Expand a compact backlog entry into a full boundary before implementing it.

## Maintaining this plan

This section owns how TODO is updated. General working principles belong in AGENTS; the review skill owns the review procedure. Keep this file focused on work that remains and dependencies on accepted decisions.

1. Give each finding a stable ID, severity, evidence status, relevant paths, expected outcome, validation criteria, and dependencies. Keep hypotheses distinguishable from validated defects; preserve reviewer classifications and record user dispositions. Do not recycle IDs.
2. Keep unassigned work compact. Before implementation, establish the assigned task's full boundary: intent, dependencies, implementation direction, non-goals, validation, and done criteria. The boundary MAY live in this file or directly in the retained review record; keep one authoritative copy and supply its location to implementing and reviewing agents. When the record owns it, identify it by task ID and leave the compact TODO finding intact until completion rather than adding temporary boundary text here. State shared group constraints once; retain distinct acceptance criteria for each task.
3. Record accepted decisions with their rationale and affected tasks in [DESIGN.md](DESIGN.md). Keep unresolved choices explicit. When a decision changes, record its supersession and update affected boundaries and dependencies before the implementation commit.
4. Use explicit dependencies and readiness to guide execution. Do not rebuild phase-closure fences or imply that every non-blocking issue must land before unrelated work can proceed.
5. Before removing a completed task's accepted boundary, preserve it under the [review skill's evidence-retention rules](.agents/skills/adversarial-review/SKILL.md#evidence-retention). In each implementation commit, remove the completed task's full active entry and execution boundary. Update references, dependencies, legacy mappings, and any affected counts or indexes. Keep at most a concise disposition or governing-document link needed for remaining work or traceability. Put implementation history in the commit and current operations in README.
6. Record deferral or acceptance without change explicitly, with the reason and any revisit trigger. Do not silently drop inherited work or treat a documentation rewrite as an implementation fix.
7. Keep evidence tied to its revision and provenance. Remove obsolete status inventories; historical review results do not certify an executor's current gates. Check local links and ID/dependency consistency after restructuring this file.

## Recommended execution workflow

Use the [grouped task execution skill](.agents/skills/grouped-task-execution/SKILL.md) for the user-recommended workflow; [AGENTS.md](AGENTS.md) owns its governance recommendation.

## Evidence provenance

The inherited findings come from the 2026-07 full-project review recorded in the former `PLAN.md`. Every one of them was revalidated by source inspection on 2026-09-11 against commit 98c4518, in the project devcontainer on Python 3.12.3. All but the entries below are implemented; the legacy mapping records each disposition.

Gate results at that revision: 197 tests pass, mypy reports no issues across 27 source files, `ruff check .` is clean, and total coverage is 98.5% statement and 92.5% branch. That revision predates the per-file branch coverage work, so its numbers do not describe the current tree.

**Validated** means source inspection or a recorded command at that revision supported the finding. **Not independently validated** identifies work accepted from a user request without separate evidence. Revalidate affected claims and remedies against the execution revision.

### Full-project assessment — 2026-09-12

Reviewed tracked application code, tests, packaging, containers, shell helpers, and documentation at **2f784f2da4b61cf773041f1e90cc5262905c4c06**, in Docker on Python 3.12.3. Three independent assessment agents covered runtime/recovery/API, media/output correctness, and tests/build/operations; the main agent consolidated findings and independently checked the cited source. This was an assessment of existing behavior, not the formal pre-commit review of an application change.

New entries below are **Validated** by source inspection at that revision; entries explicitly naming a reproduction also have bounded empirical evidence. Reproductions used extracted production functions, fake collaborators, installed dependency code, and test-owned temporary files. They covered recovery cursor forwarding, playlist follow-up loss, directory glob matches, suffix-case cleanup, language validation, filename collisions/templates, Azure cleanup, shell input handling, and invalid coverage thresholds. Redis scan semantics were checked against the [XAUTOCLAIM command reference](https://redis.io/docs/latest/commands/xautoclaim/). Temporary artifacts were removed.

The full test suite and application gates were **not run**: B2 and NB12–NB13 identify ownership defects that must be addressed before treating such a run as compliant. No live YouTube, Azure, Redis, model, media-library, or browser-profile checks were performed. Container builds, dependency installation, Python 3.10 execution, and crash durability were not exercised. Installed dependency inspection supports the specific helper/library contracts cited below, not an end-to-end deployment claim. The pre-existing untracked `.devcontainer/devcontainer-lock.json` was excluded and preserved.

**Review boundary:** record all supported findings without an issue-count cap; preserve accepted decisions and inherited IDs; change only this backlog. Findings do not authorize implementation, naming migrations, or new product contracts. Blocking entries identify unsafe validation or substantial loss/wrong-result risks in the existing application; they do not require implementing application fixes in this documentation-only review. Non-blocking entries remain real defects despite lower urgency. Behavior questions were put to the user before their disposition was recorded; the accepted decisions now in DESIGN distinguish accepted limitations from requested work. Implementation choices still called out in dependencies remain unselected.

### Simplification and architecture assessment — 2026-09-14

Dedicated follow-up at **ed9b3a1189c060adfc90e71d6a8658738cc89d31**, in the same Docker/Python 3.12.3 environment. Independent agents examined runtime architecture, media simplification, and test/build duplication; the main agent checked source dependencies and consolidated overlapping work. This pass distinguishes **validated structural observations** from **proposed improvements**: repeated code or coupling is evidenced, but a refactor's benefit is not a claim that the current behavior is incorrect or that a performance benchmark passed.

Verification used tracked-source/AST inspection, comparison of duplicated helpers/options, exhaustive registered-language conversion comparisons, and synthetic PCM samples. The waveform experiment established equivalent float32 results and an avoidable intermediate copy, not a deployment memory or speed estimate. No application gates, image builds, service calls, application-resource initialization, or host-data access were performed. Previously documented test-ownership limitations remain in force. Only TODO changes; the pre-existing untracked devcontainer lock remains excluded.

**Boundary and conclusions:** record concrete opportunities with preservation requirements and verification criteria; attach naming, SRT publication, and Azure lifecycle guidance to their existing findings rather than duplicate defects. Keep separate worker processes, the authoritative recovery/acknowledgement loop, concrete injected Redis clients, engine-specific conversions, the resident Whisper model, and pure playlist/SRT/rejection helpers. Their distinct behavior and test seams justify those boundaries. No evidence here calls for a new database, queue, plugin registry, generic engine hierarchy, or workflow framework. The user subsequently confirmed the compatibility, startup, settings-lifetime, and worker-identity directions in [D18](DESIGN.md#d18)–[D21](DESIGN.md#d21); NB25–NB27 record the resulting architecture work. Their source premises were rechecked against the working tree based on 09c1b36. Concurrent playlist work and its [D17](DESIGN.md#d17) disposition were preserved; this follow-up does not certify that work or its gates.

## Design dependencies

Accepted decisions and system constraints live in [DESIGN.md](DESIGN.md), grouped by topic. D identifiers below refer to that document. Preserve its product contracts and operating envelope, and distinguish accepted future behavior from implemented behavior.

### Investigation gates

NB2 must inventory the violations an expanded ruff selection produces before choosing the rule set; the entry does not authorize a wholesale reformat. NB3 must establish the true minimum Python version from the syntax and dependencies actually in use before changing `requires-python`. These investigations can expose new decisions; they do not authorize guessing.

## Active backlog

### Blocking

#### B5 — Title-only filenames silently alias different videos

**Severity: High. Validated — source and isolated equal-title reproduction.** [Video naming](youtube_whisperer/downloaders/video_downloader.py):55–58 and [transcript naming](youtube_whisperer/downloaders/transcript_downloader.py):186–187 derive identity solely from sanitized/truncated titles. Distinct video IDs can share MP4/SRT paths. Under worker `NEVER` semantics, the second video reuses the first media; if the first SRT is absent, captions can be paired with the wrong video. **Outcome:** preserve distinct video identities and safe repeat processing of the same video. **Acceptance:** equal titles, sanitization collisions, truncation collisions, and repeat downloads cannot substitute unrelated content. **Dependencies:** user naming/migration decision before implementation; preserve the human-browsable media-library contract and coordinate NB8. **Simplification review — 2026-09-14:** after that naming decision, use one pure naming rule for standalone MP4/SRT and combined-download paths, preserving suffixes, UTF-8 limits, and human-readable titles. The two current sanitization/truncation implementations should not evolve independently.

### Non-blocking

#### NB2 — Ruff runs with its default rule set

**Validated — no `[tool.ruff]` configuration exists at 98c4518.** Only the default `E4`, `E7`, `E9`, and `F` rules are active, so nothing enforces line length, import ordering, docstring style, or common-bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing currently produces one. **Paths:** [pyproject.toml](pyproject.toml). **Direction:** after the inventory required by the investigation gate, select a broader set. Pydocstyle with the Google convention would mechanize the docstring rule that AGENTS states in prose. **Acceptance:** `ruff check .` passes under the expanded selection and every `noqa` carries the rationale AGENTS requires. **Non-goals:** restructuring code beyond what the selected rules demand. **Current inventory — 2026-09-12:** source still uses `Any` in language-schema hooks, playlist metadata, Azure callbacks, and model parameters; several source classes lack docstrings. Tests also retain string-based patches (for example `tests/transcriber/test_model_parameters.py:7`) and alternate import forms. Inventory these separately from runtime defects, and distinguish rules Ruff can enforce from typing or test-structure work; do not claim broader lint selection alone resolves them.

#### NB3 — The declared Python floor is incompatible with the source

**Validated — source inspection at 2f784f2 on 2026-09-12.** `requires-python = ">=3.10"`, but [lang_code_adaptor.py](youtube_whisperer/adaptors/lang_code_adaptor.py) imports `Self` from `typing` at line 3; that symbol was introduced in Python 3.11. The task models and API/worker import chains therefore fail on the declared 3.10 floor. This is stronger evidence than the inherited unverified-support finding; no Python 3.10 run was performed. The devcontainer runs 3.12.3, and no environment in the repository exercises 3.10 or 3.11. The repository has no continuous integration at all, so the gates run only where an agent or the user runs them. **Paths:** [pyproject.toml](pyproject.toml), [Dockerfile](Dockerfile), [.devcontainer/](.devcontainer/). **Direction:** determine the real minimum from the code and dependencies, then either correct `requires-python` or verify the floor with a GitHub Actions matrix running the three gates across the supported versions. **Acceptance:** the declared floor is either verified by a matrix run or corrected to what is actually supported. Note [D1](DESIGN.md#d1): any CI job runs mypy against the package only.

#### NB5 — Lock-file regeneration is a side effect of creating the container

**Validated — [postCreateCommand.sh](.devcontainer/postCreateCommand.sh) at 98c4518.** Inherited from legacy finding 26. `pip freeze` rewrites `requirements.txt` on every devcontainer create, so the lock file changes on a plain rebuild rather than when dependencies actually change; the repeated "Updated dependencies" commits come from this. README now documents the behavior as it is. **Direction:** make regeneration deliberate. PLAN.md proposed an `update_lock.sh`, that script was never added, and the user has since said it is not the intended route, so the mechanism is an open question for the user. **Acceptance:** opening the devcontainer no longer modifies `requirements.txt`, and README documents how the lock file is refreshed instead.

#### NB8 — Video titles are interpreted as yt-dlp template expressions

**Severity: Medium. Validated — installed yt-dlp `prepare_filename` with synthetic metadata.** [download_video](youtube_whisperer/downloaders/video_downloader.py):33 supplies a literal path as `outtmpl`. Title `Progress %(id)s` survives sanitization, but yt-dlp expands it to `Progress AAAAAAAAAAA.mp4` while the wrapper returns `Progress %(id)s.mp4`. Follow-up work and captions use the wrong path. **Outcome:** returned media paths and caption stems match actual output even with template metacharacters. **Acceptance:** literal `%` and `%(id)s` titles, ordinary titles, and directory components resolve consistently without network calls. **Dependencies:** coordinate B5's naming decision; this escaping defect is independently reproducible.

#### NB9 — Azure duration-inspection failure leaks a started recognizer

**Severity: Medium. Validated — source and fake-recognizer reproduction (`started=1`, `stopped=0`).** [transcribe_audio_file](youtube_whisperer/transcriber/azure_transcriber.py):108–116 starts recognition, then inspects duration before entering its cleanup `try/finally`. An `sf.info` failure skips stop. **Outcome:** every started session is stopped on failure, with no output and normal worker error propagation. **Acceptance:** duration-inspection failure, startup failure, timeout, cancellation, and success have explicit owned cleanup. **Dependencies:** none; preserve the test-owned paths, synthetic settings, and callback quiescence established under B2/NB12/NB13. **Architecture review — 2026-09-14:** isolate start/wait/stop, callbacks, and result/error collection in a recognition operation; let the existing file entry point retain preflight and SRT output. Preserve synchronous completion, timeout floor/multiplier, empty-event handling, event order/logging, and cancellation details. This gives cleanup one responsibility without adding a session-class framework or moving file writes onto callback threads.

#### NB11 — Allowed video overwrites are not forwarded to yt-dlp

**Severity: Medium. Validated — source and installed yt-dlp existing-file behavior.** [download_video](youtube_whisperer/downloaders/video_downloader.py):28–40 checks overwrite permission but never configures yt-dlp to overwrite. The pathlib helper only returns permission; yt-dlp's existing-video path defaults to retaining the file. Consequently `ALWAYS` does not fulfill the wrapper's replacement contract. **Outcome:** replace existing videos only when authorized by the supplied policy. **Acceptance:** owned existing-file scenarios verify `ALWAYS` replaces and `NEVER` preserves, using the library contract without external downloads. **Dependencies:** none; mocking the entire download operation is insufficient verification.

#### NB15 — API handlers block the event loop with synchronous work

**Severity: Medium. Validated — source inspection.** [API endpoints](youtube_whisperer/api/app.py):77–240 are `async def` but call synchronous Redis/glob/directory/deletion operations directly. Slow Redis or a large traversal stalls unrelated requests in the configured single-process uvicorn service; the shared Redis pool deliberately has no read timeout for workers. **Outcome:** preserve responsiveness while blocking dependencies wait. **Acceptance:** hold one dependency behind an explicit barrier and verify an independent request completes; release and quiesce all work. **Dependencies:** preserve worker blocking-read semantics; do not impose a short shared socket timeout as a mechanical fix.

#### NB17 — Non-string language input escapes validation as TypeError

**Severity: Medium. Validated — isolated Pydantic TypeAdapter reproduction and API exception-path inspection.** [LanguageCode deserialization](youtube_whisperer/adaptors/lang_code_adaptor.py):112 raises `TypeError` for numeric, null, or collection input. Current Pydantic propagates that error instead of turning it into validation failure; the API's general handler therefore produces 500 for malformed client input. The same reproduction gives `ValidationError` for unsupported string `fr`. **Outcome:** invalid language types produce the normal client-validation response. **Acceptance:** numeric/null/list/object inputs return 422 without enqueueing; registered strings and LanguageCode instances remain accepted. **Dependencies:** none; preserve the language whitelist.

#### NB18 — Supported YouTube URL forms fail transcript ID extraction

**Severity: Medium. Validated — pure parser reproductions and installed yt-dlp support inspection.** [get_video_id](youtube_whisperer/downloaders/transcript_downloader.py):48–56 rejects bare `youtube.com`, `m.youtube.com`, and `/shorts/` URLs. [Single-video extraction](youtube_whisperer/downloaders/playlist_downloader.py):58–62 preserves the original URL, so media download can succeed before caption routing fails and dead-letters the task, including download-only work. **Outcome:** supported video URLs resolve consistently across download and transcript stages. **Acceptance:** bare/mobile/shorts/watch/live/short-link cases and malformed input use fake metadata and no service calls. **Dependencies:** none; do not expand this into arbitrary-site support.

#### NB19 — Transcript HTTP operations have no timeout

**Severity: Medium. Validated — source and installed `youtube-transcript-api==1.2.4` inspection.** [Transcript listing/fetching](youtube_whisperer/downloaders/transcript_downloader.py):92,114 use the default client. Its ordinary requests session performs GET/POST without timeouts; the application supplies neither a bounded client nor an execution deadline. A stalled response can occupy the required single YouTube worker indefinitely. **Outcome:** bound stalled caption operations. **Acceptance:** a controlled stalled HTTP double reaches a bounded, observable completion/failure and releases the worker without real YouTube access. **Dependencies:** apply [D16](DESIGN.md#d16)/NB24 after successful media download; select an appropriate finite timeout before implementation. Adding a timeout does not authorize scaling the YouTube worker.

#### NB20 — Invalid coverage thresholds disable per-file comparisons

**Severity: Low. Validated — extracted coverage parser with synthetic reports.** [check-coverage.sh](check-coverage.sh):33 accepts non-finite and out-of-range floats. A 1% report fails with `80` but reports success with `nan` or `-1`. The full script still has pytest's aggregate guard; the defect bypasses the separate per-file/branch checks when aggregate coverage passes. **Outcome:** reject invalid thresholds before running pytest. **Acceptance:** NaN, infinities, negative values and values above 100 fail clearly; valid boundaries and ordinary thresholds behave as documented. **Dependencies:** preserve [D4](DESIGN.md#d4) and the existing gate policy.

#### NB21 — Subtitle text extraction deletes valid dialogue and mishandles CRLF

**Severity: Medium. Validated — synthetic SRT shell reproductions.** [extract_subtitle_text.sh](extract_subtitle_text.sh):13 removes every numeric line, so dialogue such as `2026` disappears with cue indexes. On CRLF input, numeric indexes and blank lines survive because the regular expressions encounter carriage returns. **Outcome:** distinguish SRT structure from cue content and handle both line endings. **Acceptance:** numeric/ordinary dialogue, timestamps, indexes, blank lines, and equivalent LF/CRLF files produce the intended text. **Dependencies:** none; protect both defects in one cohesive parser boundary.

#### NB24 — Caption-service errors abort already-downloaded video work

**Severity: Medium. Validated — source inspection; requested under [D16](DESIGN.md#d16).** [Transcript lookup](youtube_whisperer/downloaders/transcript_downloader.py):89–117 handles disabled/missing transcripts but propagates other service failures through [download orchestration](youtube_whisperer/downloaders/__init__.py):26–28. After media has downloaded, the worker therefore dead-letters download-only work or skips its requested transcription fallback. **Outcome:** retain the successful media result, report the caption-service problem, and complete download-only work or enqueue the selected transcriber. **Acceptance:** listing/fetching service errors after successful download preserve the media and chosen fallback; genuine media-download, local output-write, and transcription failures still surface appropriately. **Dependencies:** [D16](DESIGN.md#d16); coordinate NB19 timeout handling and preserve the transcription-only task contract implemented by NB32, and preserve [D17](DESIGN.md#d17)'s per-video dead-lettering (a caption-service error currently dead-letters that one video). Do not catch all local/programming errors as though captions were merely unavailable.

#### NB29 — Task preparation is embedded in the HTTP route

**Severity: Low. Validated structural observation — source inspection at ed9b3a1 on 2026-09-14; proposed architecture improvement.** [add_tasks](youtube_whisperer/api/app.py):116–136 mixes pattern classification, filesystem expansion, response bookkeeping, and Redis submission. Its product rules can currently be exercised only through a module that imports FastAPI and the application's configured resources. **Outcome:** a small internal preparation operation returns routed tasks and failed patterns; the endpoint retains HTTP serialization and the existing queue adapter performs submission. **Acceptance:** preparation tests use owned files without FastAPI or Redis doubles; adapter tests preserve response/status, successful/failed ordering, URL-before-filesystem submission, metadata, and `none` handling. **Dependencies:** preserve the file-only, absolute-path resolution implemented by NB16/NB22 and preserve the [HTTP contract](DESIGN.md#http-contracts); preserve [D11](DESIGN.md#d11) best-effort submission and keep filesystem expansion in the API process. No new wire schema, workflow engine, or persisted state is proposed. Apply the same separation to per-video follow-up decisions only within NB24's assigned boundary; NB32 closes B4 through translation removal; preserve the resulting transcription-only contract under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24). `YouTubeWorker.process_video` already owns the per-video step under [D17](DESIGN.md#d17).

#### NB31 — Compose repeats the shared application-service configuration

**Severity: Low. Validated structural observation — source inventory at ed9b3a1 on 2026-09-14; proposed simplification.** [CPU Compose](docker-compose.cpu.yaml):25–83 repeats build, init, restart, volumes, environment, env-file, and Redis-health dependency settings across four application services. Existing anchors cover build and volumes separately but leave the common service block repeated. **Outcome:** one local extension mapping supplies common application defaults; service names, entrypoints, ports, and GPU overrides remain explicit. **Acceptance:** expanded CPU and GPU configurations match the originals using only synthetic environment values/files; preserve all services, volumes, health conditions, and overrides. **Dependencies:** [D10](DESIGN.md#d10) intentionally starts workers with the devcontainer. Keep Redis separate and do not add generated configuration, another Compose file, or altered resource sharing.

#### NB33 — Provisioning still installs the obsolete review plugin

**Severity: Low. Validated — source inspection at a29764e on 2026-10-02 in the devcontainer.** [Container setup](.devcontainer/postCreateCommand.sh) installs the Codex plugin and describes it as required; [tool resolver documentation](.devcontainer/link_review_tools.py) assumes its companion scripts. [D30](DESIGN.md#d30) now specifies direct CLI review. **Intent/outcome:** remove obsolete plugin provisioning and align descriptions with direct CLI dispatch. **Dependencies:** [D30](DESIGN.md#d30); inventory the resolver's unique behavior and consumers before narrowing it. **Direction:** remove plugin installation from new-container setup, preserving CLI discovery, stale-link recovery, shell-hook behavior and diagnostics that remain needed. **Non-goals:** uninstalling existing user plugins, changing authentication/model choices, unrelated dependency or worker-startup changes. **Validation:** safe tests with owned tool trees and fake commands, required application gates/review, and an isolated provisioning smoke check without host resources or real plugin installation. **Done:** fresh setup no longer requires the plugin, retained CLI resolution is verified, and documentation matches. This follow-up is recorded separately from the governance-only change; expand any unresolved implementation choices before execution.

### Nits

#### N1 — Asset cleanup reconstructs the wrong case-sensitive paths

**Severity: Low. Validated — source and owned-file reproduction.** [Suffix mapping/selection](youtube_whisperer/api/app.py):202,223 lowercases suffixes and reconstructs paths. On Linux, `video.mp4` + `video.srt` + `video.WAV` selects nonexistent `video.wav`, leaving the redundant WAV. **Outcome:** retain actual paths while matching suffixes case-insensitively. **Acceptance:** mixed-case extensions and coexisting case variants clean correctly, preserving MP4/SRT. **Dependencies:** none.

#### N2 — Empty media directories produce a fictitious filename

**Severity: Low. Validated — owned empty-directory shell reproduction.** [ls_mp4_without_srt.sh](ls_mp4_without_srt.sh):19 iterates an unmatched glob literally and prints `<directory>/*.mp4` with exit 0. **Outcome:** report only existing MP4 files missing SRT. **Acceptance:** empty directory produces no paths; missing/present SRT and filenames with spaces remain correct. **Dependencies:** none.

#### N6 — Source docstrings retain obsolete worker and failure contracts

**Severity: Low. Validated — source inspection.** [Worker entry point](youtube_whisperer/workers/__main__.py):48–58 describes slot-specific active queues and limits slot routing to Whisper/Azure, although all roles use Redis streams and the resolved consumer name. [Azure transcriber](youtube_whisperer/transcriber/azure_transcriber.py):70 says failures return `None`, although its handled failures raise. **Outcome:** describe current consumer identity and failure propagation. **Acceptance:** compare docstrings/CLI help with role dispatch and error branches. **Dependencies:** none; preserve runtime behavior.

#### N10 — ISO conversion branches repeat the same transformation

**Severity: Low. Validated — source and exhaustive registered-code comparison at ed9b3a1 on 2026-09-14.** The historical [LanguageCode](youtube_whisperer/adaptors/lang_code_adaptor.py) source conversion separately handles ISO and BCP strings, although both yield `code.split('-', 1)[0]` for every registered value. **Outcome:** remove the redundant membership branch in source ISO conversion; NB32 removed the target-conversion API under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24); the source-conversion branch remains unchanged. **Acceptance:** source output remains identical for all registered codes; retain whitelist validation, constructor/parsing normalization differences, and BCP-only conversion errors. **Dependencies:** preserve the source conversion methods retained by NB32 and keep this independent simplification distinguishable from the completed translation removal.

## Ready for implementation

NB2 and NB3 need their investigation gates cleared first. NB5 needs a user decision on the mechanism before it has a boundary.

Other new entries are compact findings, not implementation assignments: expand each boundary first and honor its explicit product-policy dependencies. Naming must be settled before its dependent implementation; playlist continuation is settled by [D17](DESIGN.md#d17). [D14](DESIGN.md#d14)/[D16](DESIGN.md#d16) settle the configuration and caption-error outcomes; N7/N8 are resolved. Expand NB24's implementation boundary before changing code.

[D18](DESIGN.md#d18)–[D21](DESIGN.md#d21) settle the compatibility, resource ownership, settings lifetime, and worker-identity choices. NB25–NB27 are implemented; retain existing Python entry points and all previously accepted product behavior except the translation interfaces explicitly removed under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24).

## Deferred, accepted, and completed dispositions

- NB4 is implemented by [DESIGN.md](DESIGN.md), the user-requested owner for system design, product contracts and topic-grouped decisions; a separate USER_STORIES document is unnecessary. README retains operating instructions and TODO retains outstanding work. N3/N5/N8 are resolved in the same documentation reorganization: build-helper references match Compose, the filename limit is stated in UTF-8 bytes, and fresh Compose setup creates its required `.env` file.

- NB27, NB28 and N12 are implemented: the base worker owns built-in identity with compatible accessors, stream polling shares payload validation and missing-group recovery, and role-dispatch tests use explicit parameter cases. DESIGN’s [worker architecture](DESIGN.md#workers-as-separate-processes) owns the current structure; recovery, acknowledgement, role processing and runtime ownership contracts remain.

- NB23, N4 and N9 are implemented: empty Whisper decoding fails before model/output work and follows durable dead-letter-before-acknowledgement handling; the decoder description reflects complete PCM buffering and its conversion avoids the redundant int16 copy. DESIGN's [Whisper input and model contract](DESIGN.md#the-whisper-model-is-kept-resident) owns the current behavior under [D15](DESIGN.md#d15).

- NB6 and NB7 are implemented: orphan scans retain and reset their cursor across polling cycles, polling requires positive seconds, and negative claim-idle values are rejected. DESIGN’s [stream recovery](DESIGN.md#redis-streams-and-a-shared-consumer-group) and README’s [direct-run timing](README.md#running-components-directly) own the current behavior.

- NB30 and N11 are implemented: title lookup, flat extraction and video download share fresh yt-dlp defaults; downloader tests use one function-scoped factory with independent records and retain option/call/result/error assertions. DESIGN's [project structure](DESIGN.md#project-structure) identifies the option-policy owner; the implementation commits record validation and mutation evidence.

- NB16 and NB22 implement file-only glob expansion with absolute API-resolved sources under [D13](DESIGN.md#d13), preserving file symlink aliases, arbitrary extensions, glob order, metadata, and failed-pattern reporting. DESIGN's [data flow](DESIGN.md#data-flow) owns the current behavior; NB29 must retain this contract.

- N7 is closed by NB25's [README configuration](README.md#configuration): direct Python/API/worker launches use exported environment variables, while Compose injects `.env` into application services under [D14](DESIGN.md#d14). N8 is closed by the explicit fresh-Compose `.env` creation step.

- NB25 implements pure domain ownership, inert ordinary imports and explicit API/worker runtime resources under [D18](DESIGN.md#d18)–[D20](DESIGN.md#d20). DESIGN’s [architecture](DESIGN.md#architecture-and-resource-ownership), [configuration ownership](DESIGN.md#settings-and-runtime-ownership) and [resident model contract](DESIGN.md#the-whisper-model-is-kept-resident) own the current behavior.

- NB26 implements neutral SRT formatting and selected-role worker loading under [D19](DESIGN.md#d19). DESIGN's [architecture](DESIGN.md#architecture-and-resource-ownership) and [SRT formatting contract](DESIGN.md#srt-as-the-output-format) own the current behavior.

- NB32 implements translation removal under [D23](DESIGN.md#d23)–[D26](DESIGN.md#d26), closing B4 by removing its operation rather than repairing target-caption routing. Tasks carry one source language and reject obsolete `mode` fields and arrow forms; existing files and caption reuse remain supported. DESIGN's [transcription and upgrade guidance](DESIGN.md#transcription-requests-and-upgrades) owns the current interfaces and rollout constraints.

- B7 is implemented: WAV conversion publishes only after successful owned ffmpeg completion, cancels/reaps interrupted children and cleans only owned stages; Azure preserves existing-good sidecar reuse and retries regenerate unpublished audio. DESIGN’s [Azure completion](DESIGN.md#azure-completion-is-synchronous-per-worker) and [atomic publication contract](DESIGN.md#srt-as-the-output-format) own the resulting behavior and [D22](DESIGN.md#d22) limits.

- NB10 is implemented: Azure carries the caller’s overwrite policy through preflight and final SRT saving; DESIGN’s [Azure completion](DESIGN.md#azure-completion-is-synchronous-per-worker) describes the behavior. Final SRT publication follows the shared [atomic publication contract](DESIGN.md#srt-as-the-output-format); NB9 lifecycle cleanup remains separate work.

- B1 is closed at the user's explicit direction on 2026-09-12: the Claude+Codex workflow was proven externally. No remaining setup blocker is carried forward.
- B3 is implemented under [D17](DESIGN.md#d17): the YouTube worker enqueues each video's follow-up as soon as that video is downloaded and dead-letters a failed video under its own URL, so a later failure no longer discards earlier progress. DESIGN's [Playlist videos succeed or fail independently](DESIGN.md#playlist-videos-succeed-or-fail-independently) owns the resulting behavior.
- The 2026-09-12 review accepts gap-bridging deduplication, dead-letter clearing races, production-worker startup in the devcontainer, best-effort batch enqueue, and manual repair of malformed Redis payloads under [D8](DESIGN.md#d8)–[D12](DESIGN.md#d12); these are not omitted defects awaiting an implicit fix.

- Legacy finding 2, path traversal in `POST /assets`, is obsolete rather than fixed: the upload endpoint no longer exists, so no client-controlled filename reaches the filesystem. Revisit only if uploads return.
- Legacy finding 11 is accepted without change under [D6](DESIGN.md#d6) and documented in its [queue contracts](DESIGN.md#http-contracts).
- Legacy finding 25 is accepted under [D5](DESIGN.md#d5); DESIGN's security and trust model section owns it.
- Legacy finding 9 is closed. The single remaining `assert` narrows a type and carries a comment saying so; it does not validate external input.
- NB1 is implemented. The three files below the branch-coverage threshold are covered and `./check-coverage.sh` passes at the default threshold; the implementation commit holds the evidence.
- B2 and NB12–NB13 are implemented as test-ownership work. Collection starts with synthetic configuration, API and Azure tests use temporary paths, tests use owned settings and clients, and Azure callback threads have owned cancellation and quiescence. README's [testing instructions](README.md#testing) cover the fresh-process requirement; the implementation commit holds current gate and mutation evidence.
- NB14 is implemented. The Whisper cache test clears its fake model on every exit, including assertion failures; its separate implementation commit holds the evidence.
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
| 11 | Accepted without change; see [D6](DESIGN.md#d6) |
| 12, 13 | Implemented; domain models live in `models.py` and the web layer is `api/` |
| 15 | Implemented; the Whisper model is cached per process |
| 16 | Implemented; the package logs and no longer prints |
| 17, 18 | Implemented; the legacy repr parser and the dead helpers are removed |
| 19 | Implemented; the test layout mirrors the package |
| 20, 22, 23, 24 | Implemented; pinned Redis image, cache-friendly Dockerfile order, corrected ignore glob, healthcheck |
| 21 | Implemented; host paths and proxies are environment-driven |
| 25 | Accepted; see [D5](DESIGN.md#d5) |
| 26 | Open; see NB5 |
| 27 | Implemented; README was rewritten and documents the previously undocumented choices |

## Integration acceptance

Review integrated changes against [DESIGN](DESIGN.md) and the current README operating instructions. Do not require every non-blocking task to land before unrelated work proceeds; record explicit defer or accept dispositions and their reasons.

AGENTS owns the required gates and the review obligation. Supplement them with checks that match what changed: queue and dead-letter behavior for worker changes, extraction behavior for downloader changes, and an end-to-end compose smoke run for infrastructure changes. Clean static analysis is not proof of correct concurrent behavior.

Keep live-service checks out of the automated suite. Exercising YouTube or Azure Speech needs explicit authorization and credentials, and must record no keys or personal media paths. Record evidence at its actual revision. Remove a completed entry in its implementation commit, keeping only the concise disposition that remaining work or traceability needs.
