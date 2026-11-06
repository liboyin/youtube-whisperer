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

NB2 must inventory the violations an expanded ruff selection produces before choosing the rule set; the entry does not authorize a wholesale reformat. That investigation can expose new decisions; it does not authorize guessing.

## Active backlog

Classification determines backlog priority, not a requirement to resolve unrelated findings in every change. Inline High/Medium/Low labels retain historical impact estimates; they do not override the Blocking/Non-blocking/Nit classification. A proposed simplification is not a runtime defect.

### Blocking

None open.

### Non-blocking

#### NB2 — Ruff runs with its default rule set

**Validated — no `[tool.ruff]` configuration exists at 98c4518.** Only the default `E4`, `E7`, `E9`, and `F` rules are active, so nothing enforces line length, import ordering, docstring style, or common-bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing currently produces one. **Paths:** [pyproject.toml](pyproject.toml). **Direction:** after the inventory required by the investigation gate, select a broader set. Pydocstyle with the Google convention would mechanize the docstring rule that AGENTS states in prose. **Acceptance:** `ruff check .` passes under the expanded selection and every `noqa` carries the rationale AGENTS requires. **Non-goals:** restructuring code beyond what the selected rules demand. **Current inventory — 2026-09-12:** source still uses `Any` in language-schema hooks, playlist metadata, Azure callbacks, and model parameters; several source classes lack docstrings. Tests also retain string-based patches (for example `tests/transcriber/test_model_parameters.py:7`) and alternate import forms. Inventory these separately from runtime defects, and distinguish rules Ruff can enforce from typing or test-structure work; do not claim broader lint selection alone resolves them.

#### NB5 — Lock-file regeneration is a side effect of creating the container

**Validated — [postCreateCommand.sh](.devcontainer/postCreateCommand.sh) at 98c4518.** Inherited from legacy finding 26. `pip freeze` rewrites `requirements.txt` on every devcontainer create, so the lock file changes on a plain rebuild rather than when dependencies actually change; the repeated "Updated dependencies" commits come from this. README now documents the behavior as it is. **Direction:** make regeneration deliberate. PLAN.md proposed an `update_lock.sh`, that script was never added, and the user has since said it is not the intended route, so the mechanism is an open question for the user. **Acceptance:** opening the devcontainer no longer modifies `requirements.txt`, and README documents how the lock file is refreshed instead. **Disposition (2026-11-06):** the user chose the mechanism, uv ([D50](DESIGN.md#d50)); NB46 resolves this finding and closes it alongside its own record.

#### NB46 — Migrate dependency management to uv

**Validated — revision aa840df on 2026-11-06; user-requested change under [D50](DESIGN.md#d50).** This is the full execution boundary and its single authoritative copy.

**Intent.** Replace the `pip freeze` snapshot with a uv lock: dependencies resolve from `pyproject.toml` into a committed `uv.lock`; the image installs that lock into `/opt/venv` through a shared `docker-build-common` helper; the devcontainer adds the locked `dev` group; and the lock changes only when someone runs `uv lock`. This resolves [NB5](#nb5--lock-file-regeneration-is-a-side-effect-of-creating-the-container).

**Dependencies.** [D50](DESIGN.md#d50) and its recorded proxy evidence; [D45](DESIGN.md#d45) and [D51](DESIGN.md#d51) (Python 3.12); the [build-helper design](DESIGN.md#build-helpers-come-from-a-shared-repository); [D10](DESIGN.md#d10) (the devcontainer starts the workers). The library helper must be pushed and tagged by the user before this repository's pin resolves without `BUILD_COMMON_CONTEXT`.

**Implementation direction — `docker-build-common` (local clone `/workspaces/docker-build-common`, branch `uv` from `main` at 1b8c221).** Add `uv_install.sh <venv-dir> [uv-export-option]...`, leaving `apt_install.sh` and `pip_install.sh` unchanged. Run from the project directory, the helper:

1. Fails with exit 2 when no venv directory is given or `uv` is not on `PATH`, and with exit 1 when `uv.lock` is missing.
2. Maps a non-empty `PYPI_PROXY` to `UV_DEFAULT_INDEX`, plus `UV_INSECURE_HOST` for the derived hostname, matching `pip_install.sh`'s `index-url`/`trusted-host` semantics. These are set for the helper's own processes only and never written to persistent uv configuration, because a persistent index would make later `uv lock` runs record the proxy URL in the lock.
3. Disables the uv cache, so no cache is left in the layer.
4. Creates the venv if absent (`uv venv --allow-existing`), honouring the consumer's `.python-version` and uv environment.
5. Exports the lock with `uv export --frozen --no-default-groups --format requirements.txt` plus forwarded options, to a temporary file it removes afterwards. `--frozen` is required because `--locked` fails behind a mirror (D50 evidence).
6. Installs the export with `uv pip sync`, which makes the venv exactly match the export and verifies every hash present. When the export contains no requirements it reports that and skips the install.

Without `--no-emit-project` the export includes the project itself, editable by default, so one helper serves both the dependency layer and the project install, and both go through the proxy. Bytecode is not precompiled, matching `pip_install.sh`. `tests/run.sh` gains cases that put a stub `uv` on `PATH` to record arguments and environment, without network access. README documents the helper. The intended release tag is `v1.2.0`: a minor version, because the change only adds a script (an assumption; the user owns tagging).

**Implementation direction — this repository.**

- `pyproject.toml`: move `dev` to `[dependency-groups]`.
- `.python-version`: `3.12`.
- Add a `uv.lock` seeded with the versions of the current `requirements.txt` snapshot, then confirm that an unconstrained `uv lock` keeps it unchanged.
- Delete `requirements.txt`.
- `Dockerfile`:
  - Copy uv 0.13.7 from `ghcr.io/astral-sh/uv`, pinned by tag and digest, into `/usr/local/bin`, because the devcontainer needs uv at runtime.
  - Set `VIRTUAL_ENV`, `UV_PROJECT_ENVIRONMENT=/opt/venv`, `PATH` and `UV_PYTHON_DOWNLOADS=never`.
  - Pre-create `/opt/venv` and the project directory owned by `ubuntu`, then run the uv steps as `ubuntu`. This avoids a recursive `chown`, which would duplicate the venv into another layer, and lets the devcontainer's `uv sync` write to the venv. The runtime user can already write the editable source tree, so this adds no new write surface.
  - Install dependencies from `pyproject.toml`, `uv.lock` and `.python-version` before `COPY . .`, then install the editable project after it.
  - Drop `python3-pip` from the apt list and remove the `python` symlink; the venv provides `python` for the Compose entrypoints and `check-coverage.sh`.
- Compose: pin the helper tag (`v1.2.0`).
- `postCreateCommand.sh`: remove the `pip freeze` line, and replace `sudo pip install -e .[dev]` with `uv sync --locked`.
- README: update the Dev Container, Compose helper pin, Local install, configuration-table and Updating dependencies sections, the last with the deliberate lock-refresh procedure (`uv lock --upgrade`, `--upgrade-package`, `uv add`).
- DESIGN: turn D50's section into current behavior and update the build-helper section.
- TODO: archive NB46 and NB5.

**Compatibility surface.** No Python API, HTTP contract or worker CLI changes. Preserved: Compose service entrypoints (`uvicorn`, `python -m youtube_whisperer.workers ...`) resolve to the venv; the project stays editable at `/workspaces/youtube-whisperer`; the `PYPI_PROXY`, `APT_PROXY` and `BUILD_COMMON_CONTEXT` variables keep their meaning for the image build. Changed and documented: `pip install -e '.[dev]'` becomes `uv sync`, since the `dev` extra no longer exists; the devcontainer's dev-tool install no longer uses `PYPI_PROXY`; and `requirements.txt` is gone.

**Non-goals.**

- Upgrading any dependency version.
- Changing the interpreter, CUDA base image or build backend (setuptools stays).
- Precompiling bytecode or adding a uv cache mount.
- Changing `pip_install.sh` or `apt_install.sh`.
- Pushing or tagging the library.
- CI.
- NB31's Compose deduplication.

**Validation.** This container has no Docker, so image builds and the library's Docker-based `tests/run.sh` cannot run here.

- Locally, with all uv state in the scratchpad:
  - Run the helper for real against the local proxy mirror into scratch venvs, covering the dependency layer and the editable project. Confirm that every artifact comes through the mirror and that a corrupted hash fails.
  - Run the stub-based helper cases.
  - Verify the lock seed against the snapshot.
  - Run the full AGENTS gates in a venv built from the lock with the `dev` group.
- The user, on the host, after the library is pushed:
  - Run `tests/run.sh`.
  - Rebuild the devcontainer, then confirm that `git status` is clean, that `uv sync --locked` succeeds, and that `python` and `uvicorn` resolve to `/opt/venv`.
  - Do a Compose smoke run of the API and every worker on GPU and CPU, plus a production image check that dev tools are absent.

Steps not performed are recorded as limitations. The adversarial review covers both repositories' diffs.

**Done criteria.**

- A devcontainer rebuild leaves the repository unmodified.
- The image installs exactly the locked runtime set through `PYPI_PROXY` when it is set.
- Gates pass from the locked dev environment.
- README describes the deliberate refresh procedure.
- The review has no unresolved Blocking findings.
- NB46 and NB5 are archived with their records.

#### NB31 — Compose repeats the shared application-service configuration

**Severity: Low. Validated structural observation — source inventory at ed9b3a1 on 2026-09-14; proposed simplification.** [CPU Compose](docker-compose.cpu.yaml):25–83 repeats build, init, restart, volumes, environment, env-file, and Redis-health dependency settings across four application services. Existing anchors cover build and volumes separately but leave the common service block repeated. **Outcome:** one local extension mapping supplies common application defaults; service names, entrypoints, ports, and GPU overrides remain explicit. **Acceptance:** expanded CPU and GPU configurations match the originals using only synthetic environment values/files; preserve all services, volumes, health conditions, and overrides. **Dependencies:** [D10](DESIGN.md#d10) intentionally starts workers with the devcontainer. Keep Redis separate and do not add generated configuration, another Compose file, or altered resource sharing.

## Readiness and unresolved choices

NB2 needs its investigation gate cleared first. NB46 is bounded and in progress; NB5 closes with it.

All entries are compact findings, not implementation assignments: expand each boundary first and honor its explicit product-policy dependencies. Naming is settled by [D47](DESIGN.md#d47); playlist continuation is settled by [D17](DESIGN.md#d17). [D14](DESIGN.md#d14)/[D16](DESIGN.md#d16) settle the configuration and caption-error outcomes; N7/N8 are resolved; NB24 implemented D16.

[D18](DESIGN.md#d18)–[D21](DESIGN.md#d21) settle the compatibility, resource ownership, settings lifetime, and worker-identity choices. NB25–NB27 are implemented; retain existing Python entry points and all previously accepted product behavior except the translation interfaces explicitly removed under [D23](DESIGN.md#d23)/[D24](DESIGN.md#d24).

## Deferred, accepted, and completed dispositions

- [B5](completed_work/B5.md) — Implemented ([D47](DESIGN.md#d47)): default downloads are named `Title [videoID].ext`, so different videos with equal or equally truncated titles get different files; an existing title-only file is still reused under its old name.
- [N1](completed_work/N1.md) — Implemented: `DELETE /assets` removes the actual on-disk MKV/WAV/MP3 files of a complete MP4 + SRT stem, matching suffixes case-insensitively; a selected file already gone is skipped.
- [N2](completed_work/N2.md) — Implemented: `ls_mp4_without_srt.sh` enables `nullglob`, so a directory without MP4 files prints nothing instead of a literal `*.mp4` path.
- [N6](completed_work/N6.md) — Implemented: worker docstrings and `--slot` help describe stream consumer identity for every role, and the Azure transcriber documents that failures raise rather than return `None`.
- [N10](completed_work/N10.md) — Implemented: `LanguageCode.get_source_as_ISO` uses one split for BCP-47 and ISO 639-1 sources; output is unchanged for every registered code.
- [N13](completed_work/N13.md) — Implemented: the four synchronous API endpoint bodies are underscore-prefixed internals, API tests follow source order, and archive mentions link their completion records.
- [N14](completed_work/N14.md) — Implemented: the shell-tool tests share one owned bash-subprocess fixture, and README describes what `extract_subtitle_text.sh` removes.
- [NB3](completed_work/NB3.md) — Implemented ([D45](DESIGN.md#d45)): `requires-python` is `>=3.12`, the only version any repository environment runs; the former `>=3.10` floor was incompatible with the source's `typing.Self` import.
- [NB8](completed_work/NB8.md) — Implemented: video titles and template metacharacters no longer alter download paths; titles never enter yt-dlp's output template.
- [NB9](completed_work/NB9.md) — Implemented: every started Azure recognition session is stopped on success, timeout, cancellation, startup failure or interruption; duration inspection precedes recognizer creation, and failures write no SRT.
- [NB11](completed_work/NB11.md) — Implemented: authorized video replacement publishes atomically after a completed staged download; failed downloads keep the previous video.
- [NB15](completed_work/NB15.md) — Implemented: every API endpoint stays a coroutine but runs its blocking Redis and filesystem work in the threadpool, so a stalled request no longer stalls independent requests; threadpool capacity bounds concurrently blocked requests.
- [NB17](completed_work/NB17.md) — Implemented: non-string language values (number, null, list, object, boolean) fail ordinary validation, so `POST /tasks` returns 422 without enqueueing.
- [NB18](completed_work/NB18.md) — Implemented: watch, live, shorts and short-link URLs on bare, `www` and mobile hosts resolve to validated video IDs; malformed URLs raise `ValueError`.
- [NB19](completed_work/NB19.md) — Implemented: every caption HTTP request defaults to a 10 s connect / 30 s read timeout ([D38](DESIGN.md#d38)) through one session per video that is closed when the lookup ends.
- [NB20](completed_work/NB20.md) — Implemented: `check-coverage.sh` rejects a non-numeric, non-finite or out-of-range `COVERAGE_THRESHOLD` before running pytest; 0 to 100 inclusive remain valid and an empty value keeps 80.
- [NB21](completed_work/NB21.md) — Implemented: subtitle text extraction drops only cue indexes, timing lines and blank separators, so numeric and arrow-bearing dialogue survive and CRLF input yields the same LF output as LF input.
- [NB24](completed_work/NB24.md) — Implemented ([D16](DESIGN.md#d16), [D39](DESIGN.md#d39)): caption-service errors after a successful download are logged and treated as missing captions, so download-only work completes and Whisper/Azure follow-ups are queued; other failures still dead-letter that video.
- [NB29](completed_work/NB29.md) — Implemented ([D42](DESIGN.md#d42)): `POST /tasks` preparation lives in the FastAPI/Redis-free `task_preparation` module; the endpoint keeps HTTP serialization and URL-before-filesystem submission, and `api.app.resolve_filesystem_tasks` forwards the same function.
- [NB33](completed_work/NB33.md) — Implemented: standalone Codex installation replaces plugin provisioning and extension-link repair.
- [NB34](completed_work/NB34.md) — Implemented: `youtube_whisperer/publication.py` owns target resolution, mode retention, create-if-absent and replacement for video, SRT and WAV publication; each caller keeps its stage creation and cleanup.
- [NB35](completed_work/NB35.md) — Implemented ([D43](DESIGN.md#d43)): a missing consumer group is created from stream ID `0`, so a task appended to a stream recreated without its group (for example by a submission racing `DELETE /tasks`) is delivered instead of stranded as pending.
- [NB36](completed_work/NB36.md) — Implemented ([D46](DESIGN.md#d46)): pathlib-extensions `truncate_filename` keeps only extension-like suffixes, so long titles containing dots get video and SRT names within 220 bytes instead of failing.
- [NB37](completed_work/NB37.md) — Implemented ([D46](DESIGN.md#d46)): pathlib-extensions owns the publication helpers and the `resolve_overwrite_mode` preflight; `youtube_whisperer.publication` forwards them and the seven repeated preflights are gone.
- [NB38](completed_work/NB38.md) — Implemented ([D48](DESIGN.md#d48)): overwrite parameters take pathlib-extensions `OverwritePolicy` (pin `fff2bf6`), former `PROMPT` defaults are `NEVER`, and `RENAME` is rejected before any work.
- [NB39](completed_work/NB39.md) — Implemented ([D48](DESIGN.md#d48)): video, SRT and WAV publish through pathlib-extensions `StagedFile` in private `.staging-<random>` directories; yt-dlp and ffmpeg still write under names that keep titles out of templates and the caller's suffix for container inference.
- [NB40](completed_work/NB40.md) — Implemented ([D48](DESIGN.md#d48)): the `youtube_whisperer.publication` forwarder is removed, so nothing in this project imports the library's `publication` module, which the library will deprecate and remove.
- [NB41](completed_work/NB41.md) — Implemented: video, SRT and WAV publication leave output preparation to `StagedFile`, so under `NEVER` a read-only competing SRT that appears during the work is kept instead of raising `PermissionError`.
- [NB42](completed_work/NB42.md) — Implemented ([D49](DESIGN.md#d49)): only the `OverwritePolicy.ALWAYS` and `NEVER` members are accepted, by identity, so stale `OverwriteMode` members and strings raise `ValueError` before any work instead of publishing numbered copies; WAV conversion checks the policy before its input.
- [NB43](completed_work/NB43.md) — Implemented ([D49](DESIGN.md#d49)): `save_segments_as_srt` and `deduplicate_srt_file` default to `ALWAYS` like `publish_srt_text`, so in-place deduplication works without an explicit policy.
- [NB44](completed_work/NB44.md) — Implemented ([D49](DESIGN.md#d49)): the Azure worker reuses a sidecar WAV through `save_as_wav_file(..., NEVER)` instead of its own existence check; the source must now exist even when its WAV does.
- [NB45](completed_work/NB45.md) — Implemented ([D49](DESIGN.md#d49)): video and WAV publication name their stage files through pathlib-extensions `StagedFile(..., name=...)` (pin `c679a0e`) instead of renaming inside the stage directory.
- [Earlier dispositions and legacy mapping](completed_work/history.md#deferred-accepted-and-completed-dispositions) — Historical closures and accepted limitations predating per-task completion records; retained without inventing missing evidence.

## Integration acceptance

Review integrated changes against [DESIGN](DESIGN.md) and the current README operating instructions. Do not require every non-blocking task to land before unrelated work proceeds; record explicit defer or accept dispositions and their reasons.

AGENTS owns the required gates and the review obligation. Supplement them with checks that match what changed: queue and dead-letter behavior for worker changes, extraction behavior for downloader changes, and an end-to-end compose smoke run for infrastructure changes. Clean static analysis is not proof of correct concurrent behavior.

Keep live-service checks out of the automated suite. Exercising YouTube or Azure Speech needs explicit authorization and credentials, and must record no keys or personal media paths. Record evidence at its actual revision. Close entries under [Maintaining this plan](#maintaining-this-plan).
