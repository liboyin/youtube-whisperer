# NB3 — The declared Python floor is incompatible with the source

## Origin

A 2026-09 assessment ([historical assessments](history.md#evidence-provenance)) classified NB3 as Non-blocking, Validated by source inspection at `2f784f2`. `pyproject.toml` declared `requires-python = ">=3.10"`, but [lang_code_adaptor.py](../youtube_whisperer/adaptors/lang_code_adaptor.py) imports `Self` from `typing`, which Python 3.11 introduced, so the task models and the API/worker import chains could not load on the declared floor. TODO directed an investigation of the real minimum from code and dependencies, followed by either a corrected floor or a GitHub Actions matrix verifying it.

## Decision

On 2026-10-12 the user decided to simply raise the declared floor to 3.12, recorded as [D45](../DESIGN.md#d45). That supersedes the investigation gate and the CI-matrix option. Python 3.12 is the only version any repository environment runs: the devcontainer runs 3.12.3, and the [Dockerfile](../Dockerfile) installs Ubuntu 24.04's system `python3`, which is 3.12.

## Boundary

- **Intent:** declare `requires-python = ">=3.12"`.
- **Compatibility surface:** installation metadata only; pip now refuses Python older than 3.12. No public Python API, HTTP contract or CLI behavior changes, and runtime behavior on 3.12 is unchanged.
- **Non-goals:** a CI matrix, testing 3.11 or older, Dockerfile or devcontainer changes, `requirements.txt` changes, and broader ruff rule selection (NB2).

## Change

- [pyproject.toml](../pyproject.toml): `requires-python = ">=3.12"`.
- [runtime.py](../youtube_whisperer/runtime.py) imports `Self` from `typing` instead of `typing_extensions`. Ruff infers its target version from `requires-python`, and `ruff check --show-settings` showed it moving from 3.10 to 3.12. Under that target, ruff 0.16.10 reported UP035 on the old import. On 3.12.3, `typing.Self is typing_extensions.Self` is true, so behavior is unchanged. `typing_extensions` was never a declared dependency; it is only a transitive pin in `requirements.txt`.
- README's local-install section states the 3.12 requirement instead of calling the floor unresolved. DESIGN gains D45, and D1's applicability column names the mypy gate rather than NB3.

## Validation and provenance

Environment: Linux Docker devcontainer, Python 3.12.3, ruff 0.16.10, mypy 2.4.0.

- **Baseline** at `14f89d1` with a clean tracked tree:
  - `./check-coverage.sh -q -p no:cacheprovider` passed 886 tests, with 99.6% statement and 98.7% branch coverage in total and every file passing.
  - `mypy youtube_whisperer` (30 source files) and `ruff check .` were clean.
- **Intermediate candidate** with only the pyproject change: the coverage gate and mypy passed, but `ruff check .` failed with UP035 at `runtime.py:6`. That led to the import change above.
- **Frozen candidate:** the dirty tree on `14f89d1`, patch sha256 `74bddfec…699c`. It passed the coverage gate (886 passed, 99.6% / 98.7%, `runtime.py` at 100%), mypy (30 files), `ruff check .` and `git diff --check`. The only warning was the pre-existing third-party StarletteDeprecationWarning. One D45 sentence was added after the gate run. That change is Markdown only and is not a gate input.
- `setuptools.config.pyprojecttoml.read_configuration` reads `>=3.12`.

No mutation evidence was required: no test changed, and no high-impact runtime invariant was added.

## Review

- **Reviewer:** a new Codex session, `01a13065-e8df-7ea2-b77c-3dcaf01ac1d8`, model `gpt-6.1-sol`, reasoning effort `high`. Model and effort come from the dispatch arguments, because the reviewer could not observe them. Exit status 0. This was a full first assessment of the frozen candidate.
- **Reviewer checks, all in scratch on Python 3.12.3:**
  - It built a wheel and confirmed `Requires-Python: >=3.12` in the metadata.
  - Version-specifier checks rejected 3.10 and 3.11 and admitted 3.12.0, 3.12.3 and 3.13.0.
  - Ruff inferred 3.12 and accepted `runtime.py`.
  - The 22 runtime tests passed (seed 12345), with imports verified to come from scratch.
  - It confirmed that `typing.Self is typing_extensions.Self`.
- **Verdict:** no Blocking findings, Non-blocking findings or Nits.
- **Integrity:** the main agent's repository snapshot after the review matched the frozen pre-review snapshot exactly.

## Limitations and cleanup

Only Python 3.12.3 was executed. Metadata admits newer versions, but nothing here verifies runtime compatibility on them. The repository still has no CI, so the gates run only where an agent or the user runs them. The reviewer deleted its scratch copy. Working evidence (prompt, report, JSONL transcript and snapshots) stayed in the session's temporary scratchpad. Its lifetime is limited, and this record retains the essential results.
