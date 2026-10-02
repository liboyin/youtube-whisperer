This file owns the working principles for this repository. All agents MUST follow it and explicit user instructions. CAPITALIZED requirement words have the meanings defined by BCP 14 (RFC 2119 and RFC 8174).

# Document Boundaries

- **AGENTS.md:** concise working principles and required standards.
- **[Grouped task execution skill](.agents/skills/grouped-task-execution/SKILL.md):** the recommended workflow for selecting and executing related TODO tasks and reviewing the integrated group.
- **[Adversarial review skill](.agents/skills/adversarial-review/SKILL.md):** how to conduct review, including dispatch, snapshots, investigation, triage, and reporting.
- **[TODO.md](TODO.md):** future work, accepted decisions, dependencies, execution boundaries, and its own maintenance rules.
- **[README.md](README.md):** current architecture, dataflow, design assumptions, and build, run, and test procedures.

Link to the owning document instead of duplicating its procedure. Operational instructions do not override the safety and ownership principles here.

# Scope and Decisions

- If not running in a Docker container, stop and confirm with the user before continuing.
- This repository assumes execution inside its devcontainer with harness permissions set to Full Access or bypass. If the active harness imposes restrictions, follow its enforced policy and report the configuration mismatch.
- Read relevant code and documentation and inspect repository status before editing. Preserve unrelated work.
- Each change MUST have a boundary: intent, dependencies, non-goals, validation strategy, and done criteria. Revalidate written tasks against the affected code; do not implement them mechanically or broaden their material scope unilaterally.
- State assumptions. Confirm unresolved choices that materially affect scope, architecture, dataflow, correctness, security, or user-visible behavior before dependent work; continue independent work where possible.
- Accepted decisions and user authorization persist. Do not ask again about settled choices. Document superseding decisions and their reasoning before committing the affected change.
- Non-material assumptions MAY be made when repository evidence supports them and they preserve the requested outcome. Name the assumption, evidence, and effect in the handoff.
- Bounded subtasks SHOULD use subagents when independent work or investigation justifies the handoff cost. Closely coupled tasks touching the same code MAY share one implementation agent. The main agent remains accountable for integration and verification.
- For a group of related TODO tasks, follow the recommended [grouped task execution workflow](.agents/skills/grouped-task-execution/SKILL.md), unless the user specifies another approach.

# Design and Documentation

- Prefer the simplest cohesive implementation within the assigned scope. Give each function, class, and module a clear responsibility; prefer pure logic, isolated side effects, and minimal mocking over unnecessary abstractions.
- Respect lint limits without splitting cohesive code solely for length. A narrow exception MUST explain the responsibility or invariant it preserves; avoid blanket disables. Avoid `Any` or `type: ignore` type annotations.
- Before removing a layer, identify all unique behavior it carries, including copy, errors, ordering, timing, diagnostics, and API- or CLI-visible behavior. Give retained behavior an explicit owner and preserve its verification.
- Verify changing language, framework, library, and service assumptions empirically or against version-appropriate documentation.
- Update documentation when the change makes it stale. Distinguish current behavior, accepted future decisions, proposals, and unverified hypotheses.
- Markdown documentation MUST use one source line per prose paragraph (no hard-wrapped in-paragraph line breaks). Preserve structural line breaks required by Markdown, including headings, lists, tables, blockquotes, and fenced code blocks.
- Verify current empirical claims before recording them. Historical evidence MUST identify its revision, relevant environment, provenance, and limitations; it does not certify current validation.
- New or changed non-test functions, methods, and classes MUST have Google-style docstrings covering purpose and any non-obvious contracts, side effects, or constraints. Test names MUST describe the protected behavior and each test keeps a one-line docstring; comments should explain non-obvious reasons or trade-offs.

# Test Guidelines

- Tests MUST protect behavior or an invariant and fail when it breaks. Prefer controlled inputs, injected clocks, and explicit completion over elapsed-time waits.
- Added or changed high-impact invariants MUST have targeted mutation evidence in an isolated scratch copy: prioritize risks such as data loss, security violations, incorrect acknowledgement, and concurrency or resource-ownership failures. For other changes, the reviewer MAY require mutation evidence when ordinary tests provide doubtful protection. Reverts, plausible regressions, and over-restrictions are prompts for choosing useful mutants, not mandatory categories. Record the protected invariant and relevant behavioral failure; one mutant MAY protect multiple assertions. Assign one primary producer of required mutation evidence per cohesive candidate; the [review skill](.agents/skills/adversarial-review/SKILL.md#evidence-retention) owns independent checking, filling evidence gaps, additional probes and optional reuse.
- Before removing or weakening coverage, demonstrate that a mutant breaking the protected property still fails another test. A surviving mutant requires investigation, not automatic removal of coverage.
- Tests MUST import the module under test as `import youtube_whisperer.my_module as testee`, call it as `testee.function_name`, and patch its attributes with `patch.object(testee, 'attribute', ...)`. Order test functions to match the source file's function order.
- Automated tests MUST NOT reach external services such as YouTube or Azure Speech, a real Redis server, a real Whisper model, or any path outside a test-owned temporary directory, even temporarily.
- Use test-owned state for filesystem paths, environment variables, settings, and queue clients; prefer fixtures such as `tmp_path` and `monkeypatch` that own their teardown. Snapshot/restore is permitted only for owned state. Do not seed real configuration to prove non-access, and do not leave files, environment variables, or streams behind. A scratch checkout alone does not isolate inherited environment variables, mounted host data, or external services.
- Shared asynchronous resources and process-global doubles MUST have per-test ownership, synchronized access, cancellation, quiescence, and local accounting for late work. These guarantees MUST hold after timeouts and failures; a completion signal alone does not prove that callbacks or background work have stopped. Tests run in random order under `pytest-randomly`, so order-dependent state is a defect rather than a flake.
- `check-coverage.sh` owns the executable coverage policy; planned changes belong in TODO. Statement and branch coverage MUST each reach the threshold for every measured file and for the project; coverage.py reports line coverage as statement coverage. Exclusions MUST have a narrow rationale and an end-to-end smoke check validated when the exclusion changes; directory location alone does not justify excluding application logic, and unperformed manual checks MUST be recorded as limitations.

# Validation and Review

- Before implementation, establish a passing baseline for the relevant checks on the starting state; record its revision, any in-scope uncommitted inputs, the checks selected, and why they cover the affected behavior. Use the full gate suite for broad changes or uncertain scope. Run tests only under the ownership rules above. A failing baseline SHOULD be fixed in a separate, authorized change first. Evidence reuse is optional under the [review skill](.agents/skills/adversarial-review/SKILL.md#evidence-retention); rerun checks when establishing equivalence is harder.
- Use focused checks during development. The final non-trivial code, test, or configuration candidate MUST pass the coverage gate (`./check-coverage.sh`), `mypy youtube_whisperer`, and `ruff check .`. Inspect per-file coverage and warnings; resolve new source warnings and explain accepted tooling warnings.
- Every independently committed non-trivial code, test, or configuration change MUST pass the [review procedure](.agents/skills/adversarial-review/SKILL.md#procedure) before commit. Tightly coupled tasks delivered as one cohesive change MAY share an integrated review; a further group review is required only for integration behavior or risks not already covered. A change is non-trivial if it could affect runtime behavior, test guarantees, build/configuration output, security, concurrency, state/data flow, or user-visible behavior. Verified cosmetic follow-ups MAY reuse passed gates and review under the [review scope rules](.agents/skills/adversarial-review/SKILL.md#review-scope). When uncertain, run the gates and review.
- The reviewer owns classification and verdict; the main agent owns independent investigation, implementation, and finding dispositions. After non-trivial fixes or rollback, repeat full gates and obtain an updated verdict under the [review skill](.agents/skills/adversarial-review/SKILL.md#reviewer-session). Non-blocking findings and Nits MAY be deferred with a recorded reason and revisit trigger, and MUST be reported to the user. Confirm dispositions that materially change scope, behavior, architecture, or accepted risk. Finish only when no Blocking finding remains and every finding has a disposition. Never silently discard or reclassify a finding.
- Documentation-only changes and read-only assessments are exempt from application gates and formal adversarial review. Verify their claims, references, completeness, and diff instead. Report what was actually checked.
- Verify success with checks that distinguish failure. Explain non-zero exits, verify absence directly, and verify rollback against the recorded pre-change state.
- Never point a development or test run at real host data: the media library behind `ASSETS_DIR`, the browser profile behind `FIREFOX_PROFILE_DIR`, or the host model cache. NEVER read or copy that browser profile; it holds live session cookies. Treat every value in `.env` as a secret: do not echo, log, commit, or transmit it. `docker compose down -v` destroys the Redis volume holding queued tasks and pending-entry state, so it requires explicit user authorization.
- Clean up owned processes and disposable artifacts while preserving the [review skill's retained evidence](.agents/skills/adversarial-review/SKILL.md#evidence-retention) and requested deliverables. Identify owned PIDs before using `kill`; NEVER use `pkill -f`. Re-check this file and the task boundary before finishing.

# Version Control

- Keep functionally independent changes in separate, self-contained commits once implemented, validated, and documented. Honor requests to leave drafts uncommitted.
- Stage explicit paths, inspect the staged diff and repository status immediately before committing, and exclude unrelated work. NEVER use `git add -A` or `git commit -a`.
- Commit messages MUST start with `<Claude/Codex/...>: <one-line summary>`, followed by a blank line and explanatory paragraphs. Do not add a `Co-Authored-By` line.
