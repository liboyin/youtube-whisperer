# TODO — Future Work

Read [AGENTS.md](AGENTS.md), [DESIGN.md](DESIGN.md) and the relevant [README](README.md) operating instructions before accepting an implementation task. This file owns outstanding work, unresolved choices and task boundaries. DESIGN owns system design, product contracts and accepted user decisions; AGENTS and the [adversarial review skill](.agents/skills/adversarial-review/SKILL.md) own working policy and review.

This file replaces `PLAN.md` and its phase sequence. Dependencies below govern execution. A recorded finding is not permission to combine unrelated changes or redesign the service. Accept a bounded assignment, re-read its code, and implement one independent change per commit. Expand a compact backlog entry into a full boundary before implementing it.

## Maintaining this plan

This section owns how TODO is updated. General working principles belong in AGENTS; the review skill owns the review procedure. Keep this file focused on work that remains and dependencies on accepted decisions.

1. Give each finding a stable ID, severity, evidence status, relevant paths, expected outcome, validation criteria, and dependencies. Keep hypotheses distinguishable from validated defects; preserve reviewer classifications and record user dispositions. Do not recycle IDs.
2. Keep unassigned work compact. Before implementation, establish the assigned task's full boundary: intent, dependencies, implementation direction, affected compatibility surface, non-goals, validation, and done criteria. The compatibility surface names every public Python API ([D18](DESIGN.md#d18)), HTTP contract or CLI behavior whose signature or semantics the change could affect, and states which are preserved; a low internal call count does not make a public function internal. The boundary MAY live in this file or directly in the retained review record; keep one authoritative copy and supply its location to implementing and reviewing agents. When the record owns it, identify it by task ID and leave the compact TODO finding intact until completion rather than adding temporary boundary text here. State shared group constraints once; retain distinct acceptance criteria for each task.
3. Record accepted decisions with their rationale and affected tasks in [DESIGN.md](DESIGN.md). Keep unresolved choices explicit. When a decision changes, record its supersession and update affected boundaries and dependencies before the implementation commit.
4. Use explicit dependencies and readiness to guide execution. Do not rebuild phase-closure fences or imply that every non-blocking issue must land before unrelated work can proceed.
5. When closing a task, create `completed_work/<ID>.md` in the same commit that removes its full active entry and execution boundary. Preserve its origin, accepted boundary and superseding decisions, revalidation, implementation or other disposition, validation commands and results with revision/environment provenance, required or performed mutation evidence, review findings and their validation/dispositions, limitations, and cleanup. State when checks or review were not performed and why; an explicit review waiver is not a passed review. Retain essential evidence in the record or durable linked artifacts under the [review skill's evidence-retention rules](.agents/skills/adversarial-review/SKILL.md#evidence-retention); temporary paths alone are not a completion archive. Omit inapplicable sections. Each task keeps its own record and acceptance evidence. Link shared evidence by section instead of repeating it, identifying the applicable candidate and any differences; separately committed tasks retain their own validation, mutation outcomes and review verdict. Sharing a record section does not establish eligibility to reuse validation. Leave one source line summarizing the outcome and linking the record under dispositions. Update references, dependencies, legacy mappings, and affected counts or indexes; current operations belong in README. Use stable headings for linked sections; short fields may remain inline. [NB33](completed_work/NB33.md) illustrates a full record, and [N10](completed_work/N10.md) links shared evidence.
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

#### NB20 — Invalid coverage thresholds disable per-file comparisons

**Severity: Low. Validated — extracted coverage parser with synthetic reports.** [check-coverage.sh](check-coverage.sh):33 accepts non-finite and out-of-range floats. A 1% report fails with `80` but reports success with `nan` or `-1`. The full script still has pytest's aggregate guard; the defect bypasses the separate per-file/branch checks when aggregate coverage passes. **Outcome:** reject invalid thresholds before running pytest. **Acceptance:** NaN, infinities, negative values and values above 100 fail clearly; valid boundaries and ordinary thresholds behave as documented. **Dependencies:** preserve [D4](DESIGN.md#d4) and the existing gate policy.

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

#### N2 — Empty media directories produce a fictitious filename

**Severity: Low. Validated — owned empty-directory shell reproduction.** [ls_mp4_without_srt.sh](ls_mp4_without_srt.sh):19 iterates an unmatched glob literally and prints `<directory>/*.mp4` with exit 0. **Outcome:** report only existing MP4 files missing SRT. **Acceptance:** empty directory produces no paths; missing/present SRT and filenames with spaces remain correct. **Dependencies:** none.

## Readiness and unresolved choices

NB2 and NB3 need their investigation gates cleared first. NB5 needs a user decision on the mechanism before it has a boundary.

All entries are compact findings, not implementation assignments: expand each boundary first and honor its explicit product-policy dependencies. Naming must be settled before its dependent implementation; playlist continuation is settled by [D17](DESIGN.md#d17). [D14](DESIGN.md#d14)/[D16](DESIGN.md#d16) settle the configuration and caption-error outcomes; N7/N8 are resolved; NB24 implemented D16.

[D18](DESIGN.md#d18)–[D21](DESIGN.md#d21) settle the compatibility, resource ownership, settings lifetime, and worker-identity choices. NB25–NB27 are implemented; retain existing Python entry points and all previously accepted product behavior except the translation interfaces explicitly removed under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24).

## Deferred, accepted, and completed dispositions

- [N1](completed_work/N1.md) — Implemented: `DELETE /assets` removes the actual on-disk MKV/WAV/MP3 files of a complete MP4 + SRT stem, matching suffixes case-insensitively; a selected file already gone is skipped.
- [N6](completed_work/N6.md) — Implemented: worker docstrings and `--slot` help describe stream consumer identity for every role, and the Azure transcriber documents that failures raise rather than return `None`.
- [N10](completed_work/N10.md) — Implemented: `LanguageCode.get_source_as_ISO` uses one split for BCP-47 and ISO 639-1 sources; output is unchanged for every registered code.
- [N13](completed_work/N13.md) — Implemented: the four synchronous API endpoint bodies are underscore-prefixed internals, API tests follow source order, and archive mentions link their completion records.
- [NB8](completed_work/NB8.md) — Implemented: video titles and template metacharacters no longer alter download paths; titles never enter yt-dlp's output template.
- [NB9](completed_work/NB9.md) — Implemented: every started Azure recognition session is stopped on success, timeout, cancellation, startup failure or interruption; duration inspection precedes recognizer creation, and failures write no SRT.
- [NB11](completed_work/NB11.md) — Implemented: authorized video replacement publishes atomically after a completed staged download; failed downloads keep the previous video.
- [NB15](completed_work/NB15.md) — Implemented: every API endpoint stays a coroutine but runs its blocking Redis and filesystem work in the threadpool, so a stalled request no longer stalls independent requests; threadpool capacity bounds concurrently blocked requests.
- [NB17](completed_work/NB17.md) — Implemented: non-string language values (number, null, list, object, boolean) fail ordinary validation, so `POST /tasks` returns 422 without enqueueing.
- [NB18](completed_work/NB18.md) — Implemented: watch, live, shorts and short-link URLs on bare, `www` and mobile hosts resolve to validated video IDs; malformed URLs raise `ValueError`.
- [NB19](completed_work/NB19.md) — Implemented: every caption HTTP request defaults to a 10 s connect / 30 s read timeout ([D38](DESIGN.md#d38)) through one session per video that is closed when the lookup ends.
- [NB21](completed_work/NB21.md) — Implemented: subtitle text extraction drops only cue indexes, timing lines and blank separators, so numeric and arrow-bearing dialogue survive and CRLF input yields the same LF output as LF input.
- [NB24](completed_work/NB24.md) — Implemented ([D16](DESIGN.md#d16), [D39](DESIGN.md#d39)): caption-service errors after a successful download are logged and treated as missing captions, so download-only work completes and Whisper/Azure follow-ups are queued; other failures still dead-letter that video.
- [NB29](completed_work/NB29.md) — Implemented ([D42](DESIGN.md#d42)): `POST /tasks` preparation lives in the FastAPI/Redis-free `task_preparation` module; the endpoint keeps HTTP serialization and URL-before-filesystem submission, and `api.app.resolve_filesystem_tasks` forwards the same function.
- [NB33](completed_work/NB33.md) — Implemented: standalone Codex installation replaces plugin provisioning and extension-link repair.
- [NB35](completed_work/NB35.md) — Implemented ([D43](DESIGN.md#d43)): a missing consumer group is created from stream ID `0`, so a task appended to a stream recreated without its group (for example by a submission racing `DELETE /tasks`) is delivered instead of stranded as pending.
- [Earlier dispositions and legacy mapping](completed_work/history.md#deferred-accepted-and-completed-dispositions) — Historical closures and accepted limitations predating per-task completion records; retained without inventing missing evidence.

## Integration acceptance

Review integrated changes against [DESIGN](DESIGN.md) and the current README operating instructions. Do not require every non-blocking task to land before unrelated work proceeds; record explicit defer or accept dispositions and their reasons.

AGENTS owns the required gates and the review obligation. Supplement them with checks that match what changed: queue and dead-letter behavior for worker changes, extraction behavior for downloader changes, and an end-to-end compose smoke run for infrastructure changes. Clean static analysis is not proof of correct concurrent behavior.

Keep live-service checks out of the automated suite. Exercising YouTube or Azure Speech needs explicit authorization and credentials, and must record no keys or personal media paths. Record evidence at its actual revision. Close entries under [Maintaining this plan](#maintaining-this-plan).
