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

Gate results at that revision: 197 tests pass, mypy reports no issues across 27 source files, `ruff check .` is clean, and total coverage is 98.5% statement and 92.5% branch. The per-file branch shortfalls in NB1 were measured by `./check-coverage.sh` at the same revision.

**Validated** means source inspection or a recorded command at that revision supported the finding. **Not independently validated** identifies work accepted from a user request without separate evidence. Revalidate affected claims and remedies against the execution revision.

## Decisions and constraints

### Accepted user decisions — 2026-09-11

| ID | Decision | Applies to |
|---|---|---|
| D1 | Tests are not type-checked. The mypy gate covers `youtube_whisperer` only, and widening it is not planned work. | NB3 |
| D2 | The adversarial review harness is the Codex plugin for Claude Code. Antigravity is removed and is not a substitute reviewer. | B1 |
| D3 | Governance files track their ClipboardTTS counterparts. Deviate only for local project context, and record the deviation. | Documentation ownership |
| D4 | `check-coverage.sh` owns the executable coverage policy. `pyproject.toml` keeps the pytest and aggregate coverage configuration. | NB1 |

### Decisions carried forward from PLAN.md

| ID | Decision | Applies to |
|---|---|---|
| D5 | The API is unauthenticated and LAN-only by design. README owns the trust model. | legacy finding 25 |
| D6 | `clear_task_queues` snapshots and then deletes non-atomically. Accepted without change and documented as a known limitation. | legacy finding 11 |

These choices do not need to be asked again. Validate exact implementation details against the repository and version-appropriate documentation. Raise a newly discovered material trade-off before changing the boundary; do not reinterpret an accepted decision silently.

### Constraints that remain in force

- Preserve the dead-letter contract: a failed transcription reaches `GET /dead-letters` rather than being acknowledged as complete. This is what legacy finding 1 fixed.
- Preserve the XAUTOCLAIM recovery path and the conservative `worker_claim_min_idle_seconds` default that keeps it from stealing live work.
- Preserve README's operating envelope: the filesystem is the source of truth, exactly one `youtube_worker` runs, one `whisper_worker` runs per GPU, and the Whisper model stays resident per process.
- Automated tests never reach YouTube, Azure Speech, a real Redis server, or a real Whisper model. AGENTS owns this rule; do not relax it to make a test simpler.

### Investigation gates

NB2 must inventory the violations an expanded ruff selection produces before choosing the rule set; the entry does not authorize a wholesale reformat. NB3 must establish the true minimum Python version from the syntax and dependencies actually in use before changing `requires-python`. These investigations can expose new decisions; they do not authorize guessing.

## Active backlog

### Blocking

#### B1 — The Codex reviewer is not yet runnable in the devcontainer

**Validated — install attempts and command checks on 2026-09-11.** The install failure is fixed: the `installed_plugins.json` bind mount is removed, so Docker no longer creates a root-owned directory where the CLI writes its JSON file, and `postCreateCommand.sh` now adds the marketplace and installs the plugin. Both commands were verified to succeed against an unobstructed config directory and to be idempotent on a re-run, which matters because the script uses `set -e`. Two things still stand between a rebuilt container and a working reviewer. The image installs no Node.js or npm, which the plugin needs to install and drive the `codex` CLI, and `codex login` is interactive and cannot be automated. Plugin state is now container-local rather than shared with the host, so it is reinstalled on every create, and Codex credentials under `~/.codex` are not persisted either. **Paths:** [Dockerfile](Dockerfile), [postCreateCommand.sh](.devcontainer/postCreateCommand.sh), [devcontainer.json](.devcontainer/devcontainer.json). **Direction:** decide whether Node.js belongs in the shared application image or only in the development environment, then install the `codex` CLI from `postCreateCommand.sh`; consider mounting `~/.codex` so a login survives rebuilds. **Acceptance:** after a rebuild, `/codex:setup` reports Codex ready and the review skill dispatches without manual steps. **Impact while open:** AGENTS requires adversarial review before committing any non-trivial change, and the skill refuses to substitute a reviewer, so such changes cannot be committed as specified. **Disposition — 2026-09-11:** at the user's direction, this fix and the `check-coverage.sh` gate were committed while B1 is open, without adversarial review, so the container could be rebuilt and the reviewer tested. Both commits need a review once a reviewer runs.

### Non-blocking

#### NB1 — Three files are below the mandated branch-coverage threshold

**Validated — `./check-coverage.sh` at 98c4518.** Statement coverage clears 80% everywhere, but branch coverage does not, so the coverage gate fails at HEAD.

| File | Statement | Branch |
|---|---|---|
| [workers/common.py](youtube_whisperer/workers/common.py) | 92.4% | 70.0% |
| [downloaders/utils.py](youtube_whisperer/downloaders/utils.py) | 100% | 75.0% |
| [downloaders/video_downloader.py](youtube_whisperer/downloaders/video_downloader.py) | 100% | 75.0% |

**Direction:** cover the missing branches with tests that encode why the behavior matters. **Non-goals:** lowering `COVERAGE_THRESHOLD`, adding coverage exclusions, or deleting branches solely to satisfy the gate. **Acceptance:** `./check-coverage.sh` exits zero at the default threshold.

#### NB2 — Ruff runs with its default rule set

**Validated — no `[tool.ruff]` configuration exists at 98c4518.** Only the default `E4`, `E7`, `E9`, and `F` rules are active, so nothing enforces line length, import ordering, docstring style, or common-bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing currently produces one. **Paths:** [pyproject.toml](pyproject.toml). **Direction:** after the inventory required by the investigation gate, select a broader set. Pydocstyle with the Google convention would mechanize the docstring rule that AGENTS states in prose. **Acceptance:** `ruff check .` passes under the expanded selection and every `noqa` carries the rationale AGENTS requires. **Non-goals:** restructuring code beyond what the selected rules demand.

#### NB3 — The declared Python floor is unverified

**Validated — `requires-python = ">=3.10"` at 98c4518; the devcontainer runs 3.12.3.** No environment exercises 3.10 or 3.11, so syntax or library behavior newer than the declared floor would pass every local gate while breaking the stated support claim. The repository has no continuous integration at all, so the gates run only where an agent or the user runs them. **Paths:** [pyproject.toml](pyproject.toml), [Dockerfile](Dockerfile), [.devcontainer/](.devcontainer/). **Direction:** determine the real minimum from the code and dependencies, then either correct `requires-python` or verify the floor with a GitHub Actions matrix running the three gates across the supported versions. **Acceptance:** the declared floor is either verified by a matrix run or corrected to what is actually supported. Note D1: any CI job runs mypy against the package only.

#### NB4 — Product behavior has no owning document

**Not independently validated — user request, 2026-09-11.** README carries user-visible behavior implicitly alongside architecture, so there is no document that owns the product contract, and AGENTS' Document Boundaries has no entry for one. **Paths:** new `USER_STORIES.md`, [README.md](README.md), [AGENTS.md](AGENTS.md). **Direction:** capture the user-visible contract, including task submission and resolution, the queue and dead-letter endpoints, asset listing and cleanup, the language whitelist and rejection policy, and SRT as the delivered output. Link it from Document Boundaries and stop duplicating it in README. **Acceptance:** USER_STORIES owns product behavior and the other documents link rather than restate it.

#### NB5 — Lock-file regeneration is a side effect of creating the container

**Validated — [postCreateCommand.sh](.devcontainer/postCreateCommand.sh) at 98c4518.** Inherited from legacy finding 26. `pip freeze` rewrites `requirements.txt` on every devcontainer create, so the lock file changes on a plain rebuild rather than when dependencies actually change; the repeated "Updated dependencies" commits come from this. README now documents the behavior as it is. **Direction:** make regeneration deliberate. PLAN.md proposed an `update_lock.sh`, that script was never added, and the user has since said it is not the intended route, so the mechanism is an open question for the user. **Acceptance:** opening the devcontainer no longer modifies `requirements.txt`, and README documents how the lock file is refreshed instead.

### Nits

No outstanding nits.

## Ready for implementation

NB1 and NB4 are ready as written. NB2 and NB3 need their investigation gates cleared first. B1 needs an action on the host that an agent inside the container cannot perform. NB5 needs a user decision on the mechanism before it has a boundary.

## Deferred, accepted, and completed dispositions

- Legacy finding 2, path traversal in `POST /assets`, is obsolete rather than fixed: the upload endpoint no longer exists, so no client-controlled filename reaches the filesystem. Revisit only if uploads return.
- Legacy finding 11 is accepted without change under D6 and documented in README's known limitations.
- Legacy finding 25 is accepted under D5; README's security and trust model section owns it.
- Legacy finding 9 is closed. The single remaining `assert` narrows a type and carries a comment saying so; it does not validate external input.
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
