# TODO — Future Work

Read [AGENTS.md](AGENTS.md), [DESIGN.md](DESIGN.md) and the relevant [README](README.md) operating instructions before accepting an implementation task. This file owns outstanding work, unresolved choices and task boundaries. DESIGN owns system design, product contracts and accepted user decisions; AGENTS and the [adversarial review skill](.agents/skills/adversarial-review/SKILL.md) own working policy and review.

This file replaces `PLAN.md` and its phase sequence. Dependencies below govern execution. A recorded finding is not permission to combine unrelated changes or redesign the service. Accept a bounded assignment, re-read its code, and implement one independent change per commit. Expand a compact backlog entry into a full boundary before implementing it.

## Maintaining this plan

This section owns how TODO is updated. General working principles belong in AGENTS; the review skill owns the review procedure. Keep this file focused on work that remains and dependencies on accepted decisions.

1. Give each finding a stable ID, severity, evidence status, relevant paths, expected outcome, validation criteria, and dependencies. Keep hypotheses distinguishable from validated defects; preserve reviewer classifications and record user dispositions. Do not recycle IDs.
2. Keep unassigned work compact. Before implementation, establish the assigned task's full boundary: intent, dependencies, implementation direction, affected compatibility surface, non-goals, validation, and done criteria. The compatibility surface names every public Python API ([D18](DESIGN.md#d18)), HTTP contract or CLI behavior whose signature or semantics the change could affect, and states which are preserved; a low internal call count does not make a public function internal. The boundary MAY live in this file or directly in the retained review record; keep one authoritative copy and supply its location to implementing and reviewing agents. When the record owns it, identify it by task ID and leave the compact TODO finding intact until completion rather than adding temporary boundary text here. State shared group constraints once; retain distinct acceptance criteria for each task.
3. Record accepted decisions with their rationale and affected tasks in [DESIGN.md](DESIGN.md). Keep unresolved choices explicit. When a decision changes, record its supersession and update affected boundaries and dependencies before the implementation commit.
4. Use explicit dependencies and readiness to guide execution. Do not rebuild phase-closure fences or imply that every non-blocking issue must land before unrelated work can proceed.
5. When closing a task, create `completed_work/<ID>.md` in the same commit that removes its full active entry and execution boundary. Preserve its origin, accepted boundary and superseding decisions, revalidation, implementation or other disposition, validation commands and results with revision/environment provenance, required or performed mutation evidence, review findings and their validation/dispositions, limitations, and cleanup. State when checks or review were not performed and why; an explicit review waiver is not a passed review. Retain essential evidence in the record or durable linked artifacts under the [review skill's evidence-retention rules](.agents/skills/adversarial-review/SKILL.md#evidence-retention); temporary paths alone are not a completion archive. Omit inapplicable sections and link shared evidence instead of duplicating it. Tasks closed by one cohesive commit MAY share one full record: the primary task's record holds the shared decisions, validation, mutation evidence, review, limitations and cleanup, while each other task's record keeps its own origin, revalidation, boundary, change and acceptance evidence and links the shared sections ([NB8](completed_work/NB8.md)/[NB11](completed_work/NB11.md) and [NB24](completed_work/NB24.md)/[NB19](completed_work/NB19.md) are examples). Leave one source line summarizing the outcome and linking the record under dispositions. Update references, dependencies, legacy mappings, and affected counts or indexes; current operations belong in README. [NB33](completed_work/NB33.md) is an example of the record format.
6. Record deferral or acceptance without change explicitly, with the reason and any revisit trigger. Closing an obsolete task or accepting it without change requires the completion record and disposition link above; deferred work remains active. Do not silently drop inherited work or treat a documentation rewrite as an implementation fix.
7. Keep evidence tied to its revision and provenance. Remove obsolete status inventories; historical review results do not certify an executor's current gates. Check local links and ID/dependency consistency after restructuring this file.

## Recommended execution workflow

Use the [grouped task execution skill](.agents/skills/grouped-task-execution/SKILL.md) for the user-recommended workflow; [AGENTS.md](AGENTS.md) owns its governance recommendation.

## Evidence provenance

Backlog entries retain their original assessment status, not a claim of current validation. **Validated** means source inspection or a recorded command supported the finding at the cited revision; **Not independently validated** means accepted from a user request without separate evidence. Revalidate before implementation. Historical line numbers are locators at their assessment revision, not current source links.

See [historical assessments](completed_work/history.md#evidence-provenance) for the 2026-07/09 reviews, revisions, environments, methods and limitations. Their old gate results and test-ownership blockers do not certify or block today's tree.

## Design dependencies

Accepted decisions and system constraints live in [DESIGN.md](DESIGN.md), grouped by topic. D identifiers below refer to that document. Preserve its product contracts and operating envelope, and distinguish accepted future behavior from implemented behavior.

### Investigation gates

NB2 must inventory the violations an expanded ruff selection produces before choosing the rule set; the entry does not authorize a wholesale reformat. NB3 must establish the true minimum Python version from the syntax and dependencies actually in use before changing `requires-python`. These investigations can expose new decisions; they do not authorize guessing.

## Active backlog

Classification determines backlog priority, not a requirement to resolve unrelated findings in every change. Inline High/Medium/Low labels retain historical impact estimates; they do not override the Blocking/Non-blocking/Nit classification. A proposed simplification is not a runtime defect.

### Blocking

#### B5 — Title-only filenames silently alias different videos

**Severity: High. Validated — source and isolated equal-title reproduction.** [Video naming](youtube_whisperer/downloaders/video_downloader.py):95–96 and [transcript naming](youtube_whisperer/downloaders/transcript_downloader.py):228–229 derive identity solely from sanitized/truncated titles. Distinct video IDs can share MP4/SRT paths. Under worker `NEVER` semantics, the second video reuses the first media; if the first SRT is absent, captions can be paired with the wrong video. **Outcome:** preserve distinct video identities and safe repeat processing of the same video. **Acceptance:** equal titles, sanitization collisions, truncation collisions, and repeat downloads cannot substitute unrelated content. **Dependencies:** user naming/migration decision before implementation; preserve the human-browsable media-library contract and the literal-path staged video publication implemented by [NB8](completed_work/NB8.md)/[NB11](completed_work/NB11.md). **Simplification review — 2026-09-14:** after that naming decision, use one pure naming rule for standalone MP4/SRT and combined-download paths, preserving suffixes, UTF-8 limits, and human-readable titles. The two current sanitization/truncation implementations should not evolve independently.

### Non-blocking

#### NB2 — Ruff runs with its default rule set

**Validated — no `[tool.ruff]` configuration exists at 98c4518.** Only the default `E4`, `E7`, `E9`, and `F` rules are active, so nothing enforces line length, import ordering, docstring style, or common-bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing currently produces one. **Paths:** [pyproject.toml](pyproject.toml). **Direction:** after the inventory required by the investigation gate, select a broader set. Pydocstyle with the Google convention would mechanize the docstring rule that AGENTS states in prose. **Acceptance:** `ruff check .` passes under the expanded selection and every `noqa` carries the rationale AGENTS requires. **Non-goals:** restructuring code beyond what the selected rules demand. **Current inventory — 2026-09-12:** source still uses `Any` in language-schema hooks, playlist metadata, Azure callbacks, and model parameters; several source classes lack docstrings. Tests also retain string-based patches (for example `tests/transcriber/test_model_parameters.py:7`) and alternate import forms. Inventory these separately from runtime defects, and distinguish rules Ruff can enforce from typing or test-structure work; do not claim broader lint selection alone resolves them.

#### NB3 — The declared Python floor is incompatible with the source

**Validated — source inspection at 2f784f2 on 2026-09-12.** `requires-python = ">=3.10"`, but [lang_code_adaptor.py](youtube_whisperer/adaptors/lang_code_adaptor.py) imports `Self` from `typing` at line 3; that symbol was introduced in Python 3.11. The task models and API/worker import chains therefore fail on the declared 3.10 floor. This is stronger evidence than the inherited unverified-support finding; no Python 3.10 run was performed. The devcontainer runs 3.12.3, and no environment in the repository exercises 3.10 or 3.11. The repository has no continuous integration at all, so the gates run only where an agent or the user runs them. **Paths:** [pyproject.toml](pyproject.toml), [Dockerfile](Dockerfile), [.devcontainer/](.devcontainer/). **Direction:** determine the real minimum from the code and dependencies, then either correct `requires-python` or verify the floor with a GitHub Actions matrix running the three gates across the supported versions. **Acceptance:** the declared floor is either verified by a matrix run or corrected to what is actually supported. Note [D1](DESIGN.md#d1): any CI job runs mypy against the package only.

#### NB5 — Lock-file regeneration is a side effect of creating the container

**Validated — [postCreateCommand.sh](.devcontainer/postCreateCommand.sh) at 98c4518.** Inherited from legacy finding 26. `pip freeze` rewrites `requirements.txt` on every devcontainer create, so the lock file changes on a plain rebuild rather than when dependencies actually change; the repeated "Updated dependencies" commits come from this. README now documents the behavior as it is. **Direction:** make regeneration deliberate. PLAN.md proposed an `update_lock.sh`, that script was never added, and the user has since said it is not the intended route, so the mechanism is an open question for the user. **Acceptance:** opening the devcontainer no longer modifies `requirements.txt`, and README documents how the lock file is refreshed instead.

#### NB9 — Azure duration-inspection failure leaks a started recognizer

**Severity: Medium. Validated — source and fake-recognizer reproduction (`started=1`, `stopped=0`).** [transcribe_audio_file](youtube_whisperer/transcriber/azure_transcriber.py):108–116 starts recognition, then inspects duration before entering its cleanup `try/finally`. An `sf.info` failure skips stop. **Outcome:** every started session is stopped on failure, with no output and normal worker error propagation. **Acceptance:** duration-inspection failure, startup failure, timeout, cancellation, and success have explicit owned cleanup. **Dependencies:** none; preserve the test-owned paths, synthetic settings, and callback quiescence established under B2/NB12/NB13. **Architecture review — 2026-09-14:** isolate start/wait/stop, callbacks, and result/error collection in a recognition operation; let the existing file entry point retain preflight and SRT output. Preserve synchronous completion, timeout floor/multiplier, empty-event handling, event order/logging, and cancellation details. This gives cleanup one responsibility without adding a session-class framework or moving file writes onto callback threads.

#### NB15 — API handlers block the event loop with synchronous work

**Severity: Medium. Validated — source inspection.** [API endpoints](youtube_whisperer/api/app.py):77–240 are `async def` but call synchronous Redis/glob/directory/deletion operations directly. Slow Redis or a large traversal stalls unrelated requests in the configured single-process uvicorn service; the shared Redis pool deliberately has no read timeout for workers. **Outcome:** preserve responsiveness while blocking dependencies wait. **Acceptance:** hold one dependency behind an explicit barrier and verify an independent request completes; release and quiesce all work. **Dependencies:** preserve worker blocking-read semantics; do not impose a short shared socket timeout as a mechanical fix.

#### NB17 — Non-string language input escapes validation as TypeError

**Severity: Medium. Validated — isolated Pydantic TypeAdapter reproduction and API exception-path inspection.** [LanguageCode deserialization](youtube_whisperer/adaptors/lang_code_adaptor.py):112 raises `TypeError` for numeric, null, or collection input. Current Pydantic propagates that error instead of turning it into validation failure; the API's general handler therefore produces 500 for malformed client input. The same reproduction gives `ValidationError` for unsupported string `fr`. **Outcome:** invalid language types produce the normal client-validation response. **Acceptance:** numeric/null/list/object inputs return 422 without enqueueing; registered strings and LanguageCode instances remain accepted. **Dependencies:** none; preserve the language whitelist.

#### NB20 — Invalid coverage thresholds disable per-file comparisons

**Severity: Low. Validated — extracted coverage parser with synthetic reports.** [check-coverage.sh](check-coverage.sh):33 accepts non-finite and out-of-range floats. A 1% report fails with `80` but reports success with `nan` or `-1`. The full script still has pytest's aggregate guard; the defect bypasses the separate per-file/branch checks when aggregate coverage passes. **Outcome:** reject invalid thresholds before running pytest. **Acceptance:** NaN, infinities, negative values and values above 100 fail clearly; valid boundaries and ordinary thresholds behave as documented. **Dependencies:** preserve [D4](DESIGN.md#d4) and the existing gate policy.

#### NB21 — Subtitle text extraction deletes valid dialogue and mishandles CRLF

**Severity: Medium. Validated — synthetic SRT shell reproductions.** [extract_subtitle_text.sh](extract_subtitle_text.sh):13 removes every numeric line, so dialogue such as `2026` disappears with cue indexes. On CRLF input, numeric indexes and blank lines survive because the regular expressions encounter carriage returns. **Outcome:** distinguish SRT structure from cue content and handle both line endings. **Acceptance:** numeric/ordinary dialogue, timestamps, indexes, blank lines, and equivalent LF/CRLF files produce the intended text. **Dependencies:** none; protect both defects in one cohesive parser boundary.

#### NB29 — Task preparation remains coupled to the HTTP module

**Severity: Low. Validated structural observation — source inspection at ed9b3a1 on 2026-09-14; proposed architecture improvement.** [add_tasks](youtube_whisperer/api/app.py) coordinates classification, filesystem resolution, response bookkeeping and Redis submission. **Revalidated by source inspection at d3a1c5b:** `resolve_filesystem_tasks` already separates glob expansion, and NB25 made ordinary API imports resource-inert. Preparation still lives in the FastAPI module; the remaining proposal is separation of that coordination from HTTP, not removal of import-time resource creation. **Outcome:** a small internal preparation operation returns routed tasks and failed patterns; the endpoint retains HTTP serialization and the existing queue adapter performs submission. **Acceptance:** preparation tests use owned files without FastAPI or Redis doubles; adapter tests preserve response/status, successful/failed ordering, URL-before-filesystem submission, metadata, and `none` handling. **Dependencies:** preserve the file-only, absolute-path resolution implemented by NB16/NB22 and preserve the [HTTP contract](DESIGN.md#http-contracts); preserve [D11](DESIGN.md#d11) best-effort submission and keep filesystem expansion in the API process. No new wire schema, workflow engine, or persisted state is proposed. NB24 kept the per-video follow-up decision in the worker; any further separation of it needs its own boundary. NB32 closes B4 through translation removal; preserve the resulting transcription-only contract under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24). `YouTubeWorker.process_video` already owns the per-video step under [D17](DESIGN.md#d17).

#### NB31 — Compose repeats the shared application-service configuration

**Severity: Low. Validated structural observation — source inventory at ed9b3a1 on 2026-09-14; proposed simplification.** [CPU Compose](docker-compose.cpu.yaml):25–83 repeats build, init, restart, volumes, environment, env-file, and Redis-health dependency settings across four application services. Existing anchors cover build and volumes separately but leave the common service block repeated. **Outcome:** one local extension mapping supplies common application defaults; service names, entrypoints, ports, and GPU overrides remain explicit. **Acceptance:** expanded CPU and GPU configurations match the originals using only synthetic environment values/files; preserve all services, volumes, health conditions, and overrides. **Dependencies:** [D10](DESIGN.md#d10) intentionally starts workers with the devcontainer. Keep Redis separate and do not add generated configuration, another Compose file, or altered resource sharing.

#### NB34 — Staged-file publication is hand-copied in three places

**Severity: Low. Validated structural observation — Claude Opus 5.5 re-review of `5fdb927` and main-agent source comparison at `a424a2b` on 2026-10-11; proposed simplification.**

- **Duplication:** [video download](youtube_whisperer/downloaders/video_downloader.py) (`download_video`), [SRT publication](youtube_whisperer/adaptors/srt_deduplicator.py) (`publish_srt_text`) and [WAV conversion](youtube_whisperer/transcriber/waveform_loader.py) (`save_as_wav_file`) each repeat the same steps: mode capture, `chmod`, `os.link` create-if-absent for `NEVER`/`RENAME` with the file-collision rule, and atomic replacement otherwise. The WAV copy already expresses the collision branch differently.
- **Risk:** a future fix to one copy of this data-loss-sensitive protocol can miss the others.
- **Outcome:** one staged-file publication helper owns the shared [completion contract](DESIGN.md#srt-as-the-output-format) and [D22](DESIGN.md#d22). Each caller keeps its own stage creation and cleanup.
- **Acceptance:** the existing video, SRT and WAV publication tests pass unchanged. Mutation evidence shows that the helper's collision, mode and replacement rules are protected through every caller.
- **Dependencies:** none.
- **Revisit trigger:** the next change to any publication path.

### Nits

#### N1 — Asset cleanup reconstructs the wrong case-sensitive paths

**Severity: Low. Validated — source and owned-file reproduction.** [Suffix mapping/selection](youtube_whisperer/api/app.py):202,223 lowercases suffixes and reconstructs paths. On Linux, `video.mp4` + `video.srt` + `video.WAV` selects nonexistent `video.wav`, leaving the redundant WAV. **Outcome:** retain actual paths while matching suffixes case-insensitively. **Acceptance:** mixed-case extensions and coexisting case variants clean correctly, preserving MP4/SRT. **Dependencies:** none.

#### N2 — Empty media directories produce a fictitious filename

**Severity: Low. Validated — owned empty-directory shell reproduction.** [ls_mp4_without_srt.sh](ls_mp4_without_srt.sh):19 iterates an unmatched glob literally and prints `<directory>/*.mp4` with exit 0. **Outcome:** report only existing MP4 files missing SRT. **Acceptance:** empty directory produces no paths; missing/present SRT and filenames with spaces remain correct. **Dependencies:** none.

#### N6 — Source docstrings retain obsolete worker and failure contracts

**Severity: Low. Validated — source inspection.** **Revalidated by source inspection at d3a1c5b:** `resolve_worker_slot` and `--slot` help in the [worker entry point](youtube_whisperer/workers/__main__.py), plus the [Azure worker constructor](youtube_whisperer/workers/azure_worker.py), still describe active queues or limit slots to Whisper/Azure. All roles use stream consumer identity; `process_queue` already describes that correctly. [Azure transcriber](youtube_whisperer/transcriber/azure_transcriber.py):70 says failures return `None`, although its handled failures raise. **Outcome:** describe current consumer identity and failure propagation. **Acceptance:** compare docstrings/CLI help with role dispatch and error branches. **Dependencies:** none; preserve runtime behavior.

#### N10 — ISO conversion branches repeat the same transformation

**Severity: Low. Validated — source and exhaustive registered-code comparison at ed9b3a1 on 2026-09-14.** The historical [LanguageCode](youtube_whisperer/adaptors/lang_code_adaptor.py) source conversion separately handles ISO and BCP strings, although both yield `code.split('-', 1)[0]` for every registered value. **Outcome:** remove the redundant membership branch in source ISO conversion; NB32 removed the target-conversion API under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24); the source-conversion branch remains unchanged. **Acceptance:** source output remains identical for all registered codes; retain whitelist validation, constructor/parsing normalization differences, and BCP-only conversion errors. **Dependencies:** preserve the source conversion methods retained by NB32 and keep this independent simplification distinguishable from the completed translation removal.

## Readiness and unresolved choices

NB2 and NB3 need their investigation gates cleared first. NB5 needs a user decision on the mechanism before it has a boundary.

All entries are compact findings, not implementation assignments: expand each boundary first and honor its explicit product-policy dependencies. Naming must be settled before its dependent implementation; playlist continuation is settled by [D17](DESIGN.md#d17). [D14](DESIGN.md#d14)/[D16](DESIGN.md#d16) settle the configuration and caption-error outcomes; N7/N8 are resolved; NB24 implemented D16.

[D18](DESIGN.md#d18)–[D21](DESIGN.md#d21) settle the compatibility, resource ownership, settings lifetime, and worker-identity choices. NB25–NB27 are implemented; retain existing Python entry points and all previously accepted product behavior except the translation interfaces explicitly removed under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24).

## Deferred, accepted, and completed dispositions

- [NB8](completed_work/NB8.md) — Implemented: video titles and template metacharacters no longer alter download paths; titles never enter yt-dlp's output template.
- [NB11](completed_work/NB11.md) — Implemented: authorized video replacement publishes atomically after a completed staged download; failed downloads keep the previous video.
- [NB18](completed_work/NB18.md) — Implemented: watch, live, shorts and short-link URLs on bare, `www` and mobile hosts resolve to validated video IDs; malformed URLs raise `ValueError`.
- [NB19](completed_work/NB19.md) — Implemented: every caption HTTP request defaults to a 10 s connect / 30 s read timeout ([D38](DESIGN.md#d38)) through one session per video that is closed when the lookup ends.
- [NB24](completed_work/NB24.md) — Implemented ([D16](DESIGN.md#d16), [D39](DESIGN.md#d39)): caption-service errors after a successful download are logged and treated as missing captions, so download-only work completes and Whisper/Azure follow-ups are queued; other failures still dead-letter that video.
- [NB33](completed_work/NB33.md) — Implemented: standalone Codex installation replaces plugin provisioning and extension-link repair.
- [Earlier dispositions and legacy mapping](completed_work/history.md#deferred-accepted-and-completed-dispositions) — Historical closures and accepted limitations predating per-task completion records; retained without inventing missing evidence.

## Integration acceptance

Review integrated changes against [DESIGN](DESIGN.md) and the current README operating instructions. Do not require every non-blocking task to land before unrelated work proceeds; record explicit defer or accept dispositions and their reasons.

AGENTS owns the required gates and the review obligation. Supplement them with checks that match what changed: queue and dead-letter behavior for worker changes, extraction behavior for downloader changes, and an end-to-end compose smoke run for infrastructure changes. Clean static analysis is not proof of correct concurrent behavior.

Keep live-service checks out of the automated suite. Exercising YouTube or Azure Speech needs explicit authorization and credentials, and must record no keys or personal media paths. Record evidence at its actual revision. Close entries under [Maintaining this plan](#maintaining-this-plan).
