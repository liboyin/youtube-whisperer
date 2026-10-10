# Historical assessments and dispositions

This archive preserves the historical material moved from TODO at `d3a1c5b7fcc86172878b3630697f9707dcbf66ff`. It records prior claims and limitations, not current validation or new execution instructions. No tests or reproductions were rerun for this migration. References to “current” state below describe their original assessment or disposition; consult [DESIGN](../DESIGN.md) for current contracts and [TODO](../TODO.md) for active work. Older closures predate the per-task archive requirement; their missing evidence has not been reconstructed or certified.

## Evidence provenance

The inherited findings come from the 2026-07 full-project review recorded in the former `PLAN.md`. Every one of them was revalidated by source inspection on 2026-09-11 against commit 98c4518, in the project devcontainer on Python 3.12.3. The legacy mapping below records their dispositions; remaining work is listed in the active TODO backlog.

Gate results at that revision: 197 tests pass, mypy reports no issues across 27 source files, `ruff check .` is clean, and total coverage is 98.5% statement and 92.5% branch. That revision predates the per-file branch coverage work, so its numbers do not describe the current tree.

**Validated** means source inspection or a recorded command at that revision supported the finding. **Not independently validated** identifies work accepted from a user request without separate evidence. Revalidate affected claims and remedies against the execution revision.

### Full-project assessment — 2026-09-12

Reviewed tracked application code, tests, packaging, containers, shell helpers, and documentation at **2f784f2da4b61cf773041f1e90cc5262905c4c06**, in Docker on Python 3.12.3. Three independent assessment agents covered runtime/recovery/API, media/output correctness, and tests/build/operations; the main agent consolidated findings and independently checked the cited source. This was an assessment of existing behavior, not the formal pre-commit review of an application change.

Findings introduced by that assessment were **Validated** by source inspection at that revision; entries explicitly naming a reproduction also have bounded empirical evidence. Reproductions used extracted production functions, fake collaborators, installed dependency code, and test-owned temporary files. They covered recovery cursor forwarding, playlist follow-up loss, directory glob matches, suffix-case cleanup, language validation, filename collisions/templates, Azure cleanup, shell input handling, and invalid coverage thresholds. Redis scan semantics were checked against the [XAUTOCLAIM command reference](https://redis.io/docs/latest/commands/xautoclaim/). Temporary artifacts were removed.

At that assessment, the full test suite and application gates were **not run** because B2 and NB12–NB13 identified ownership defects; the later dispositions below record their closure. No live YouTube, Azure, Redis, model, media-library, or browser-profile checks were performed. Container builds, dependency installation, Python 3.10 execution, and crash durability were not exercised. Installed dependency inspection supports the specific helper/library contracts cited below, not an end-to-end deployment claim. The pre-existing untracked `.devcontainer/devcontainer-lock.json` was excluded and preserved.

**Review boundary:** record all supported findings without an issue-count cap; preserve accepted decisions and inherited IDs; change only this backlog. Findings do not authorize implementation, naming migrations, or new product contracts. Blocking entries identify unsafe validation or substantial loss/wrong-result risks in the existing application; they do not require implementing application fixes in this documentation-only review. Non-blocking entries remain real defects despite lower urgency. Behavior questions were put to the user before their disposition was recorded; the accepted decisions now in DESIGN distinguish accepted limitations from requested work. Implementation choices still called out in dependencies remain unselected.

### Simplification and architecture assessment — 2026-09-14

Dedicated follow-up at **ed9b3a1189c060adfc90e71d6a8658738cc89d31**, in the same Docker/Python 3.12.3 environment. Independent agents examined runtime architecture, media simplification, and test/build duplication; the main agent checked source dependencies and consolidated overlapping work. This pass distinguishes **validated structural observations** from **proposed improvements**: repeated code or coupling is evidenced, but a refactor's benefit is not a claim that the current behavior is incorrect or that a performance benchmark passed.

Verification used tracked-source/AST inspection, comparison of duplicated helpers/options, exhaustive registered-language conversion comparisons, and synthetic PCM samples. The waveform experiment established equivalent float32 results and an avoidable intermediate copy, not a deployment memory or speed estimate. No application gates, image builds, service calls, application-resource initialization, or host-data access were performed. The previously documented test-ownership limitations still applied at that assessment. Only TODO changes; the pre-existing untracked devcontainer lock remains excluded.

**Boundary and conclusions:** record concrete opportunities with preservation requirements and verification criteria; attach naming, SRT publication, and Azure lifecycle guidance to their existing findings rather than duplicate defects. Keep separate worker processes, the authoritative recovery/acknowledgement loop, concrete injected Redis clients, engine-specific conversions, the resident Whisper model, and pure playlist/SRT/rejection helpers. Their distinct behavior and test seams justify those boundaries. No evidence here calls for a new database, queue, plugin registry, generic engine hierarchy, or workflow framework. The user subsequently confirmed the compatibility, startup, settings-lifetime, and worker-identity directions in [D18](../DESIGN.md#d18)–[D21](../DESIGN.md#d21); NB25–NB27 record the resulting architecture work. Their source premises were rechecked against the working tree based on 09c1b36. Concurrent playlist work and its [D17](../DESIGN.md#d17) disposition were preserved; this follow-up does not certify that work or its gates.

## Deferred, accepted, and completed dispositions

These are the dispositions recorded in TODO before this archival move, except NB33, which remains in the [current closure index](../TODO.md#deferred-accepted-and-completed-dispositions) with its own record. That index owns new entries. Missing historical evidence has not been reconstructed.

- NB4 is implemented by [DESIGN.md](../DESIGN.md), the user-requested owner for system design, product contracts and topic-grouped decisions; a separate USER_STORIES document is unnecessary. README retains operating instructions and TODO retains outstanding work. N3/N5/N8 are resolved in the same documentation reorganization: build-helper references match Compose, the filename limit is stated in UTF-8 bytes, and fresh Compose setup creates its required `.env` file.

- NB27, NB28 and N12 are implemented: the base worker owns built-in identity with compatible accessors, stream polling shares payload validation and missing-group recovery, and role-dispatch tests use explicit parameter cases. DESIGN’s [worker architecture](../DESIGN.md#workers-as-separate-processes) owns the current structure; recovery, acknowledgement, role processing and runtime ownership contracts remain.

- NB23, N4 and N9 are implemented: empty Whisper decoding fails before model/output work and follows durable dead-letter-before-acknowledgement handling; the decoder description reflects complete PCM buffering and its conversion avoids the redundant int16 copy. DESIGN's [Whisper input and model contract](../DESIGN.md#the-whisper-model-is-kept-resident) owns the current behavior under [D15](../DESIGN.md#d15).

- NB6 and NB7 are implemented: orphan scans retain and reset their cursor across polling cycles, polling requires positive seconds, and negative claim-idle values are rejected. DESIGN’s [stream recovery](../DESIGN.md#redis-streams-and-a-shared-consumer-group) and README’s [direct-run timing](../README.md#running-components-directly) own the current behavior.

- NB30 and N11 are implemented: title lookup, flat extraction and video download share fresh yt-dlp defaults; downloader tests use one function-scoped factory with independent records and retain option/call/result/error assertions. DESIGN's [project structure](../DESIGN.md#project-structure) identifies the option-policy owner; the implementation commits record validation and mutation evidence.

- NB16 and NB22 implement file-only glob expansion with absolute API-resolved sources under [D13](../DESIGN.md#d13), preserving file symlink aliases, arbitrary extensions, glob order, metadata, and failed-pattern reporting. DESIGN's [data flow](../DESIGN.md#data-flow) owns the current behavior; NB29 must retain this contract.

- N7 is closed by NB25's [README configuration](../README.md#configuration): direct Python/API/worker launches use exported environment variables, while Compose injects `.env` into application services under [D14](../DESIGN.md#d14). N8 is closed by the explicit fresh-Compose `.env` creation step.

- NB25 implements pure domain ownership, inert ordinary imports and explicit API/worker runtime resources under [D18](../DESIGN.md#d18)–[D20](../DESIGN.md#d20). DESIGN’s [architecture](../DESIGN.md#architecture-and-resource-ownership), [configuration ownership](../DESIGN.md#settings-and-runtime-ownership) and [resident model contract](../DESIGN.md#the-whisper-model-is-kept-resident) own the current behavior.

- NB26 implements neutral SRT formatting and selected-role worker loading under [D19](../DESIGN.md#d19). DESIGN's [architecture](../DESIGN.md#architecture-and-resource-ownership) and [SRT formatting contract](../DESIGN.md#srt-as-the-output-format) own the current behavior.

- NB32 implements translation removal under [D23](../DESIGN.md#d23)–[D26](../DESIGN.md#d26), closing B4 by removing its operation rather than repairing target-caption routing. Tasks carry one source language and reject obsolete `mode` fields and arrow forms; existing files and caption reuse remain supported. DESIGN's [transcription and upgrade guidance](../DESIGN.md#transcription-requests-and-upgrades) owns the current interfaces and rollout constraints.

- B7 is implemented: WAV conversion publishes only after successful owned ffmpeg completion, cancels/reaps interrupted children and cleans only owned stages; Azure preserves existing-good sidecar reuse and retries regenerate unpublished audio. DESIGN’s [Azure completion](../DESIGN.md#azure-completion-is-synchronous-per-worker) and [atomic publication contract](../DESIGN.md#srt-as-the-output-format) own the resulting behavior and [D22](../DESIGN.md#d22) limits.

- NB10 is implemented: Azure carries the caller’s overwrite policy through preflight and final SRT saving; DESIGN’s [Azure completion](../DESIGN.md#azure-completion-is-synchronous-per-worker) describes the behavior. Final SRT publication follows the shared [atomic publication contract](../DESIGN.md#srt-as-the-output-format); NB9 lifecycle cleanup remains separate work.

- B1 is closed at the user's explicit direction on 2026-09-12: the Claude+Codex workflow was proven externally. No remaining setup blocker is carried forward.
- B3 is implemented under [D17](../DESIGN.md#d17): the YouTube worker enqueues each video's follow-up as soon as that video is downloaded and dead-letters a failed video under its own URL, so a later failure no longer discards earlier progress. DESIGN's [Playlist videos succeed or fail independently](../DESIGN.md#playlist-videos-succeed-or-fail-independently) owns the resulting behavior.
- The 2026-09-12 review accepts gap-bridging deduplication, dead-letter clearing races, production-worker startup in the devcontainer, best-effort batch enqueue, and manual repair of malformed Redis payloads under [D8](../DESIGN.md#d8)–[D12](../DESIGN.md#d12); these are not omitted defects awaiting an implicit fix.

- Legacy finding 2, path traversal in `POST /assets`, is obsolete rather than fixed: the upload endpoint no longer exists, so no client-controlled filename reaches the filesystem. Revisit only if uploads return.
- Legacy finding 11 is accepted without change under [D6](../DESIGN.md#d6) and documented in its [queue contracts](../DESIGN.md#http-contracts).
- Legacy finding 25 is accepted under [D5](../DESIGN.md#d5); DESIGN's security and trust model section owns it.
- Legacy finding 9 is closed. The single remaining `assert` narrows a type and carries a comment saying so; it does not validate external input.
- NB1 is implemented. The three files below the branch-coverage threshold are covered and `./check-coverage.sh` passes at the default threshold; the implementation commit holds the evidence.
- B2 and NB12–NB13 are implemented as test-ownership work. Collection starts with synthetic configuration, API and Azure tests use temporary paths, tests use owned settings and clients, and Azure callback threads have owned cancellation and quiescence. README's [testing instructions](../README.md#testing) cover the fresh-process requirement; the implementation commit holds historical gate and mutation evidence.
- NB14 is implemented. The Whisper cache test clears its fake model on every exit, including assertion failures; its separate implementation commit holds the evidence.
- Legacy finding 26 remains open as NB5. Other inherited findings are implemented, obsolete, or accepted as recorded in the mapping below.
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
| 11 | Accepted without change; see [D6](../DESIGN.md#d6) |
| 12, 13 | Implemented; domain models live in `models.py` and the web layer is `api/` |
| 15 | Implemented; the Whisper model is cached per process |
| 16 | Implemented; the package logs and no longer prints |
| 17, 18 | Implemented; the legacy repr parser and the dead helpers are removed |
| 19 | Implemented; the test layout mirrors the package |
| 20, 22, 23, 24 | Implemented; pinned Redis image, cache-friendly Dockerfile order, corrected ignore glob, healthcheck |
| 21 | Implemented; host paths and proxies are environment-driven |
| 25 | Accepted; see [D5](../DESIGN.md#d5) |
| 26 | Open; see NB5 |
| 27 | Implemented; README was rewritten and documents the previously undocumented choices |
