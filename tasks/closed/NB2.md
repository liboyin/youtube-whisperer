# NB2 — Ruff runs with its default rule set

**Outcome:** Implemented ([D61](../../DESIGN.md#d61)): the Ruff configuration is youtube-collector's, and `ruff check .` passes under it.

**Evidence:** validated at `98c4518`, where no `[tool.ruff]` configuration existed. Only the default `E4`, `E7`, `E9` and `F` rules were active. Nothing enforced line length, import order, docstring style or common bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing produced one.

**Revalidation, 2026-11-23:** Ruff 0.17.6's default rule set is wider than that evidence states. It also includes EXE001, PLW1510 and D419, which T2 (review tooling) had to satisfy. youtube-collector selects `E`, `W`, `F`, `I`, `B`, `UP` and `D`, with the Google convention. A trial of that docstring selection here found 103 findings in the package and the skill scripts, and 150 with the tests.

- **Paths:** [pyproject.toml](../../pyproject.toml).
- **Investigation gate:** inventory the violations that an expanded selection produces before you choose the rule set. The task does not authorize a wholesale reformat. The investigation can expose new decisions. It does not authorize guessing them.
- **Direction:** after the inventory, select a broader rule set. pydocstyle with the Google convention would enforce the docstring rule that AGENTS states in prose. When it does, delete that prose rule.
- **Acceptance:** `ruff check .` passes under the expanded selection, and every `noqa` carries the rationale that AGENTS requires.
- **Non-goals:** restructuring code beyond what the selected rules demand.
- **Inventory, 2026-09-12:** the source still uses `Any` in the language-schema hooks, the playlist metadata, the Azure callbacks and the model parameters. Several source classes lack docstrings. Tests still patch by string, for example `tests/transcriber/test_model_parameters.py:7`, and use other import forms.
- **Scope of the inventory:** separate these items from runtime defects. Distinguish the rules that Ruff can enforce from typing work and test-structure work. Do not claim that a broader selection alone resolves them.

## Origin and boundary

The user asked on 2026-11-23 to execute NB2. The investigation compared candidate rule sets on this repository and on youtube-collector. The user then updated collector's lock to Ruff 0.17.6, which matches this repository's, and asked that the two projects' Ruff rules be lined up. The rule set is recorded as [D61](../../DESIGN.md#d61).

- **Intent:** the `[tool.ruff]` sections of this repository and youtube-collector are identical, and `ruff check .` passes under them.
- **Dependencies:** youtube-collector at `08bdbfa`, whose configuration selects `E`, `W`, `F`, `I`, `B`, `UP` and `D` with the Google convention and line length 120. Ruff 0.17.6 in both locks.
- **Implementation direction:**
  - Copy collector's `[tool.ruff]` sections verbatim into `pyproject.toml`.
  - Apply Ruff's own fixes for `D212`, `D200` and `W293`.
  - Write the missing module, package, class and function docstrings, and the two missing argument descriptions.
  - Wrap each line that `E501` reports. Ruff exempts a line that ends in a URL, and those lines stay. Code statements go through `ruff format --range` limited to the statement's line, with quote style preserved. Strings, comments and docstrings are wrapped by hand.
  - Keep the two `str` and `Enum` classes, with a `noqa: UP042` that states the reason.
  - Leave the OpenAPI document unchanged. FastAPI publishes an endpoint's docstring, and Pydantic publishes a model's class docstring, as descriptions. `add_tasks` keeps its docstring without its injected Redis client, under `noqa: D417`. `AddTasksResponse`, `TaskQueues` and `DeadLetter` stay without docstrings, under `noqa: D101`.
  - Make the AGENTS docstring rule identical to collector's, which no longer names the style that Ruff enforces.
- **Decisions within DESIGN's latitude (assumptions):**
  - "Line up" means adopting collector's selection exactly, the option recommended to the user. A broader shared selection is a later change for both repositories.
  - Ruff's selection replaces its default set, so 291 default rules outside the seven families stop running here, as they already do in collector. The tree passed all of them at `3bc4dc3`.
  - `StrEnum` is not adopted. `str()` and f-strings of a `(str, Enum)` member give `TranscriberType.WHISPER`, and of a `StrEnum` member give `whisper`. `workers/__main__.py` formats a `WorkerRole` into an error message.
- **Compatibility surface:** the OpenAPI document that `GET /openapi.json` serves stays byte-identical. No public Python API, other HTTP contract, CLI behavior, setting or on-disk layout changes. The CLI help text keeps its exact wording, split into adjacent literals.
- **Non-goals:** a wholesale reformat, `ruff format` as a gate, a broader rule set, changes to Ruff's version, and typing or test-structure work from the 2026-09-12 inventory.
- **Validation:** the three gates. An AST comparison of every tracked Python file with docstrings stripped, against `HEAD`. For the test scripts that run in a child process, a comparison of the ASTs of the embedded source. A comparison of the OpenAPI document with `HEAD`'s, with a control that a model docstring changes it. The documentation check.
- **Mutation evidence:** none required. The change alters no runtime behavior and no test assertion.
- **Done:** the gates and the review pass, the user has reviewed the AGENTS diff, and the change is committed with its closed record.

## Implementation

- **Configuration:** `pyproject.toml` gains collector's `[tool.ruff]`, `[tool.ruff.lint]` and `[tool.ruff.lint.pydocstyle]` sections, without the comment that cites AGENTS for the docstring convention ([Review](#review), finding 2).
- **Docstrings:** Ruff's fixes moved 64 summaries to the first line (`D212`), joined 3 one-line docstrings (`D200`) and removed whitespace on 12 blank lines (`W293`). 57 modules and packages, 7 classes, 7 functions, 4 methods and 2 initializers gained docstrings. One argument description names its parameter correctly, and one summary gained its blank line.
- **Line length:** `ruff format --range L:1-(L+1):1`, with quote style preserved, wrapped the statement on each reported line, bottom-up in each file. 31 strings, comments, docstrings and statements that the formatter cannot split were wrapped by hand.
- **Exceptions:** `noqa: UP042` on `TranscriberType` and `WorkerRole`, because `str()` and f-strings give `TranscriberType.WHISPER` for a `(str, Enum)` member and `whisper` for a `StrEnum` member. `noqa: D417` on `add_tasks`, and `noqa: D101` on `AddTasksResponse`, `TaskQueues` and `DeadLetter`, because FastAPI and Pydantic publish those docstrings in the OpenAPI document.
- **Governance:** the AGENTS docstring rule reads as collector's. It no longer names the style that Ruff enforces.
- **DESIGN:** D61.

## Validation

Run on 2026-11-23 in the default devcontainer, with Python 3.12.3 and Ruff 0.17.6, on `3bc4dc3` plus the candidate.

- `./check-coverage.sh`: 1055 passed, 99.7% statement and 99.2% branch, the same as the baseline at `3bc4dc3`. `mypy youtube_whisperer`: no issues in 31 files. `ruff check .`: clean.
- `ruff check . --isolated --line-length 120`, Ruff's default set, reports only the 2 `noqa: UP042` comments as unused (`RUF100`), because that set does not enable `UP042`. The candidate therefore also passes the 291 default rules that the selection drops.
- The AST of every tracked Python file, with docstrings stripped, equals `HEAD`'s, except in five test files. In those, a string constant holds source that a child process runs, and the dedented embedded source parses to the same AST as at `HEAD`.
- The OpenAPI document of `app.openapi()`, printed with socket connects refused, is byte-identical to `HEAD`'s, at 9,565 bytes. A control with a docstring on `DeadLetter` adds a description line.
- The shared documentation check at agent-workflow-common `b14b8a9`: 56 files and no problems. `git diff --check`: clean.

## Mutation evidence

None required. The change alters no runtime behavior and no test assertion, as the AST and OpenAPI comparisons show.

## Review

Codex `gpt-6.2-sol` at high effort, a first assessment and one follow-up. The integrity snapshots matched after each.

1. **Blocking, fixed.** The added docstrings changed the OpenAPI document: the `POST /tasks` description named the injected Redis client, and three response schemas gained descriptions. The `noqa: D417` and `noqa: D101` exceptions restore it, and the reviewer confirmed byte-identical bodies with an independent probe and control.
2. **Nit, fixed here by the user.** The copied Ruff comment said that AGENTS requires Google-style docstrings, which the AGENTS rule no longer states. The user removed it on 2026-11-23. Collector's `pyproject.toml` at `08bdbfa` still carries it, so the two configurations differ by that comment until collector removes it. Their settings are identical.
3. **Nit, resolved.** Four test lines over 120 characters end in URLs, which `E501` exempts. The boundary now says to wrap each line that `E501` reports.

Verdict after the follow-up: no Blocking finding.

## Limitations and cleanup

- The selection drops 291 rules of Ruff's default set, as collector's does. A broader selection shared by both repositories is not part of this task.
- The probes ran in the scratchpad and in the reviewer's scratch copies, which were removed.
