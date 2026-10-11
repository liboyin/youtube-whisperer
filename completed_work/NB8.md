# NB8 — Video titles no longer act as yt-dlp template expressions

**Origin:** TODO recorded that `download_video` passed the title-derived destination to yt-dlp as `outtmpl`, so a title such as `Progress %(id)s` downloaded to `Progress AAAAAAAAAAA.mp4` while callers used the literal path. NB8 was executed together with [NB11](NB11.md) as one cohesive change to the same function, under one shared boundary and review. This record holds the shared evidence.

**User decisions (2026-10-10):** fix NB8 and NB11 with a staged download followed by atomic publication, rather than escaping the template and forwarding yt-dlp's `overwrites` flag. Implementation was delegated to the Codex CLI (`gpt-6.1-sol`), and review went to a separate Codex session.

**Revalidation:** the main agent checked installed yt-dlp 2026.08.19 at `e3648cc` with synthetic metadata and no network access:

- `YoutubeDL.prepare_filename` turned a literal `/a/Progress %(id)s.mp4` template into `/a/Progress AAAAAAAAAAA.mp4`, and `/a/%%.mp4` into `/a/%.mp4`.
- yt-dlp also applies `os.path.expandvars` and `expanduser` to the template (`YoutubeDL._outtmpl_expandpath`). With `FOO=EXPANDED`, `/a/Price $FOO.mp4` became `/a/Price EXPANDED.mp4`.
- `$$` is not an escape: it survives expansion as `$$`. Escaping `%` alone therefore cannot make a title-bearing template literal, and an environment value containing `/` could redirect output into other directories.

The user then amended `e3648cc` into `81b99de`. The diff touched only governance prose, README, completed-work records and a compose comment, so the downloader, its tests, DESIGN and TODO were byte-identical.

**Boundary:** the shared intent was for a video download to produce exactly the requested literal path, whatever the title contains, and to replace an existing video only when policy authorizes it, without losing the previous video if the replacement fails.

- **Direction:** download into a freshly created hidden `.video-<random>` stage directory beside the resolved destination, using the fixed name `video.mp4` with `%` escaped. Reject any parent path that yt-dlp would change by variable or home expansion before creating the stage. Require a regular staged file after the download and context exit, then publish under [D22](../DESIGN.md#d22). Always remove the owned stage directory.
- **Non-goals:**
  - B5 naming or migration, and title sanitization changes;
  - stage scavenging and power-loss durability;
  - refactoring SRT/WAV publication;
  - worker `NEVER` semantics, the caption path, and playlists;
  - network access in tests.
- **NB8 acceptance:** titles and directories containing `%`, `%%`, `%(id)s`, unset `$NAME` and ordinary text resolve through yt-dlp's real `prepare_filename` to the stage and publish at the literal target. A parent containing a set `$NAME` fails with `ValueError` before any stage or downloader exists.

**Change:**

- [video_downloader.py](../youtube_whisperer/downloaders/video_downloader.py): `download_video` now stages and publishes as described above. Cookie discovery at invocation, fresh options, the exact format selection, context-exit exception identity, the early refusal, and `download_video_with_default_title`'s naming and return value are unchanged.
- [test_video_downloader.py](../tests/downloaders/test_video_downloader.py): tests now use a per-test subclass of the real `YoutubeDL` (`auto_init=False`). It evaluates templates with the installed library and writes synthetic bytes only where `prepare_filename` directs, inside `tmp_path`.
- [DESIGN](../DESIGN.md#filenames-are-truncated) documents video staging and the hidden-stage limitation, extends the completion contract and D22 to video, and leaves naming solely with B5.

**Integration notes:** API glob resolution (`glob.glob`) does not descend into hidden stage directories unless a pattern names them. Asset cleanup only selects `.mkv/.wav/.mp3` siblings of a stem that has both `.mp4` and `.srt`. `list_assets` can show a stage while a download is running or after an abrupt exit.

## Validation

Environment: Linux Docker devcontainer, Python 3.12.3, yt-dlp 2026.08.19, pytest 9.1.1, pytest-randomly 5.0.0. The only warning in every full run was the pre-existing Starlette/httpx test-client deprecation.

| Run | Revision / candidate | Result |
| --- | --- | --- |
| Main-agent baseline | `e3648cc` (test inputs identical to `81b99de`) | `./check-coverage.sh` 587 passed, 99.5% statement / 97.1% branch; mypy clean (29 files); ruff clean |
| Implementer baseline | `81b99de` | seed 251694660, 587 passed, same coverage; mypy and ruff clean |
| Implementer final | candidate (tests SHA-256 `86b448e1…`) | seed 2082648300, 635 passed, 99.5% / 97.2%; mypy, ruff, `git diff --check` clean |
| Main-agent final (frozen) | `81b99de` + candidate | seed 638922892, 635 passed, 99.5% / 97.2%; `video_downloader.py` 47/47 statements, 12/12 branches; mypy, ruff, `git diff --check` clean |

Frozen candidate SHA-256 values:

- `video_downloader.py`: `586ffb91a63c36787636e8dd870f61e62b1bdaad9bea9c5584b3ab762f544339`
- `test_video_downloader.py`: `2aaded0493c86b6c055a5b36fb8663ca9ebe9ccb223cb9db06eed7d35024cd49`
- `DESIGN.md`: `6c70dcf63f59ba872aeed3e73a0168b0bef2f6bce2df893a7e7fd7955fc8bc1e`

During integration the main agent added five blank lines so top-level test functions are separated by two. Rebuilding the implementer's file from its retained patch and diffing it against the frozen file showed only those blank lines. Source and DESIGN were identical, so the mutation evidence below applies unchanged.

## Mutation evidence

Codex session `01a12644-1b21-7720-bc93-ade188caaa83` (`gpt-6.1-sol`, high effort) produced the evidence. It worked in an owned scratch copy of the tracked candidate with no `.env` or ignored content, keeping the `tests/conftest.py` bootstrap. Each run was a fresh `python -m pytest <selection> --no-cov -p no:cacheprovider --randomly-seed=2082648300`, with scratch-root `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE=1`, and a scratch-owned `TMPDIR` and `--basetemp`. A scratch-only socket guard blocked network connections. A `pytest_sessionfinish` hook printed `ACTUAL_IMPORT_PROVENANCE youtube_whisperer.downloaders.video_downloader=<scratch>/…/video_downloader.py` in every run. The unmutated baseline passed 55 cases. Every mutant was restored before the next run.

| Mutant | Invariant | Test | Behavioral failure |
| --- | --- | --- | --- |
| a: inside the downloader context, write the stage and `os.replace(stage, target)` before `ydl.download` | Failed `ALWAYS` keeps previous bytes | `test_download_video_propagates_error_and_exits_context` | `assert b'premature publication' == b'previous video'` |
| b: `os.link` → `os.replace` under `NEVER`/`RENAME` | `NEVER` keeps a competing file | `…preserves_competing_file…[file-never]` | `assert b'new video' == b'competing video'` |
| c1: `outtmpl` without `%` → `%%` | Percent in a directory stays literal | `…publishes_literal_names…[dir%%-ordinary]` | Real `prepare_filename` wrote to `dir%`; `FileNotFoundError: Download did not produce a regular staged video` |
| c2: remove the expansion guard | Expanding parent rejected before staging | `test_download_video_rejects_expanding_parent_before_staging` | Stage created and `$NB8_SET` expanded (inside `tmp_path`); `FileNotFoundError` instead of `ValueError` |
| d: `shutil.rmtree(stage_dir)` → `pass` | Failure removes the owned stage | `test_download_video_propagates_error_and_exits_context` | `assert [PosixPath('…/.video-p0a528ar')] == []` |
| e: drop `stage.chmod(mode)` | Replacement keeps permission bits | `…replaces_authorized_existing_file_and_preserves_mode[always]` | `assert 384 == 416` (0o600 vs 0o640) |
| f: drop `.resolve()` on the target | D22 follows symlinks; hardlinked alias unchanged | `…resolves_symlink_and_leaves_hardlinked_alias_unchanged` | `assert link.is_symlink()` failed |

No run failed containment or provenance, and no mutant survived. No existing coverage was weakened: tests that previously mocked `prepare_output_file` now run against real owned files.

## Review

Reviewer: Codex session `01a1264d-7588-7200-999f-5417e4bda0e8` (`gpt-6.1-sol`, high effort), started without the main agent's conversation. It performed a full first assessment of the dirty tree on `81b99de`, covering the three candidate paths.

- **Mutation evidence:** the reviewer reconstructed the candidate and all seven mutants, matched their recorded hashes, confirmed that the tests differed only by blank lines, and accepted the kills without replay.
- **Focused run:** in its own scratch copy (seed 638922892, network blocked, scratch import provenance verified), the current downloader tests passed 55 cases.
- **Additional probes:** six scratch-only probes passed:
  - discovery, constructor, context-exit and `chmod` failures each preserved the previous bytes and removed the stage;
  - installed `YoutubeDL.process_info` with postprocessing, given owned transfer I/O, published the exact literal target under both `ALWAYS` and `NEVER`.

**Verdict: no blocking findings; no Non-blocking findings or Nits.** With no findings, nothing needed a disposition. The main agent's post-review integrity comparison matched the pre-review snapshot exactly: HEAD, status, empty staged diff, modes and hashes.

## Re-review

- **Why:** the user requested a fresh adversarial review with Claude Opus 5.5 (2026-10-11), because the original implementer and reviewer were both Codex `gpt-6.1-sol`.
- **Reviewer:** a Claude Opus 5.5 subagent (Claude Code Agent tool), started without the main agent's conversation and using the dispatch rules of the [review skill](../.agents/skills/adversarial-review/SKILL.md). The first dispatch failed with an API certificate error before doing any work, and it was relaunched once unchanged.
- **Target:** commit `5fdb927`, as a full first assessment.
- **Gates (main agent):** run on a `git archive 5fdb927` export with `PYTHONPATH` set to it. `./check-coverage.sh` gave 635 passed (seed 1900862736), total 99.5% statement / 97.2% branch; mypy and ruff were clean.
- **Reviewer verification:** reviewer scratch export, devcontainer, Python 3.12.3, yt-dlp 2026.08.19, with network connections blocked by a scratch-only socket guard.
  - **Path probe:** 1,463 parent-directory names ran through the real `download_video` and the real `prepare_filename`. 80 were rejected before staging and 1,383 were published at the literal target.
  - **Merge probe:** a real format-selection and FFmpeg-merge run with synthetic media fixtures.
  - **Mutants:** supplied mutants a–f were accepted, and b and e were replayed and killed. The reviewer's own mutants g (title enters the template), i (swallow every `FileExistsError`) and k (`RENAME` loses create-if-absent) were killed. Mutant j (second `prepare_output_file` removed) survived and was investigated: it affects only a dangling symlink whose destination parent is missing, and it mirrors the SRT path. No finding was raised.
- **Findings:**
  1. **Non-blocking:** video publication is a third hand-copied implementation of the staged-file protocol shared with SRT and WAV.
     - **Validated** by source comparison.
     - **Disposition:** deferred as [TODO NB34](../TODO.md#nb34--staged-file-publication-is-hand-copied-in-three-places), because it needs a three-module refactor outside this boundary. Revisit trigger: the next change to any publication path.
  2. **Nit:** the DESIGN contract that publication follows downloader context exit had no protecting test. Mutant h, which publishes inside the `with` block, passed all 55 tests.
     - **Validated and fixed** by `test_download_video_publishes_only_after_downloader_context_exit` (`ALWAYS` over an existing file, `NEVER` into an absent target).
     - **Main-agent mutation evidence:** a scratch export of the follow-up candidate, seed 424242, with provenance verified for `video_downloader`. Baseline 57 passed; mutant h failed 2 (`assert b'new video' == b'previous video'`); after restoring the source, 57 passed.
     - **Reviewer check:** the reviewer also killed variants that published early only through `os.replace` and only through `os.link`.
  3. **Nit:** TODO B5 cited stale line references (`video_downloader.py:55–58`). **Validated and fixed**, together with the stale transcript reference in the same sentence.
- **Verdict:** the follow-up assessment found no blocking findings and nothing new. The first assessment and the follow-up left HEAD, status and the candidate diff unchanged.

## Limitations and cleanup

- No live extraction, browser-cookie loading, network transfer or FFmpeg merge was exercised. Tests exercise yt-dlp's template evaluation and file processing with synthetic metadata.
- A parent directory whose path contains `$NAME` of a set variable is now rejected rather than silently redirected.
- An abrupt exit can leave a hidden `.video-<random>` directory, which is not scavenged.
- New videos keep the downloader's file permissions; approved replacements keep the previous bits.
- Title collisions remain under B5.

Both scratch trees were deleted and their absence verified, and no owned processes remain. Working-record logs, raw mutant diffs and probe sources stayed in the session's temporary scratchpad and are not retained. This record preserves the essential definitions, commands, seeds, provenance and outcomes.
