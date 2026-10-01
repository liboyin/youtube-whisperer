---
name: adversarial-review
description: Adversarial review and reviewer-owned triage of non-trivial code, test, or configuration changes. Use before commit when AGENTS.md requires independent review; return findings without changing the repository.
---

# Adversarial Review

Return a reviewer-triaged report without changing the repository. The reviewer MAY propose remedies but MUST NOT implement them. The main agent investigates Blocking findings, handles Nits when practical, and surfaces Non-blocking findings to the user as defined in step 4.

## Procedure

1. **Gate, freeze, and snapshot.** Before dispatching the reviewer, the main agent MUST run every gate required by `AGENTS.md` against the exact target state and confirm that each passes. If any gate fails, do not dispatch the reviewer; resolve the failure first. After the gates pass, freeze repository edits and record `git status`, content hashes for dirty tracked files and in-scope untracked files, the paths of out-of-scope untracked files, and relevant PIDs/listeners. Do not inspect or hash ignored untracked content.

2. **Dispatch one reviewer.** Tell it to read this skill but execute only step 3 and return the defined report; the main agent owns steps 1, 2, and 4. Launch the reviewer agent without inherited conversation history using the applicable supported harness:

   - **Codex:** spawn the reviewer as a native subagent with `spawn_agent`, using `fork_turns: "none"` and explicit `model: "gpt-6.1-sol"` and `reasoning_effort: "high"` overrides. Native subagents inherit the current Full Access environment; no sandbox configuration is required.
   - **Claude Code with the Codex plugin:** dispatch the reviewer with `/codex:rescue --fresh --write --model gpt-6.1-sol --effort high <review prompt>` or a fresh underlying companion `task` command with the same model and effort. Never use `--resume` or `--resume-last`.

   Track any background reviewer invocation through completion and capture its exit status and report before dispositioning findings; starting the task is not evidence that review completed.

   When the Codex plugin is not installed, install it without asking, then verify:

   ```bash
   claude plugin marketplace add openai/codex-plugin-cc
   claude plugin install codex@openai-codex
   claude plugin list
   ```

   The plugin is [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc), which also documents the `codex` binary it drives and the `codex login` that authenticates it. Authentication is interactive and cannot be automated. If any step fails, stop and tell the user which command to run manually; do not work around a failed install.

   **Scratch copy.** The reviewer writes only outside the repository, to build and test its copy of the target; native Codex inherits that access and Claude Code gets it from `--write`. Every dispatch MUST require the reviewer to keep the repository read-only, work only in that copy, and delete it at exit. Build the copy from the tracked target state plus the in-scope staged and unstaged changes, adding only the in-scope untracked files the dispatch names and never ignored or out-of-scope content; a reviewer that cannot create it returns `Review blocked`. The reviewer is trusted here: step 1's snapshot and step 4's comparison detect accidental mutation, they are not a security boundary.

   A scratch copy does not itself satisfy AGENTS' test-ownership rules: focused tests and mutation runs also need test-owned paths, settings, and service doubles. Do not copy `.env`, browser profiles, media libraries, or model caches into the scratch copy, or run it against those resources through inherited configuration.

   **Sandbox fallback.** A container that forbids unprivileged user namespaces cannot start the reviewer's `bwrap` sandbox: every command fails and it returns `Review blocked` having inspected nothing. Confirm that first, for example that `unshare --user true` fails for root too, so an ordinary scratch-copy failure is not mistaken for it. The companion pins its sandbox mode in source, so no plugin flag reaches it and the reviewer must be driven through the CLI the plugin itself drives: `codex exec --dangerously-bypass-approvals-and-sandbox --model gpt-6.1-sol -c model_reasoning_effort="high"`. That run is fresh unless resumed and has no `--effort` flag; add `--skip-git-repo-check` when its working directory is outside a repository, and bypassing the sandbox already grants what `--write` would.

   Disabling the sandbox removes the reviewer's containment and lets it write wherever the user can, so the main agent MUST explain that and obtain explicit user confirmation first; the authorization then persists under AGENTS' Scope and Decisions. The step 1 snapshot and step 4 comparison become the only detection of repository mutation, so the main agent MUST compare them before trusting the report. Prefer removing the cause, since a container permitted to create user namespaces runs the documented dispatch unchanged; this SHOULD NOT become the default path.

   Pass only:

   - Repository path and target: dirty tree, commit, or range.
   - In-scope paths and any unrelated dirty paths to ignore.
   - Purpose of the change in a few sentences.

   Add undocumented constraints, accepted findings not to re-raise, or prior mutation evidence only when nonempty. Do not inline the diff, full conversation, architecture summaries available in the repository, suspected defects, or the main agent's conclusions.

   The reviewer MAY ask for further information when missing context could affect a finding or verdict. Reply with the minimum factual context and record the exchange under **Assumptions**.

   If `gpt-6.1-sol` or the applicable dispatch mechanism is still unavailable after that install attempt, stop and ask the user. Do not substitute or issue a verdict.

3. **Review.** The reviewer:

   - Reads `AGENTS.md`, the complete target diff, in-scope untracked files, and relevant source, tests, documentation, and configuration. Never reads ignored untracked content.
   - Takes a constructively adversarial stance: assume the change may be wrong and actively try to falsify it with counterexamples, boundary and failure cases, invariant violations, state transitions, tests that can pass for the wrong reason, and mutants. For this project, scrutinize Redis stream and consumer-group semantics, acknowledgement and dead-letter ordering, worker process and concurrency boundaries, filesystem and path handling, and external-service failure paths where relevant. Never manufacture findings, treat taste as a defect, or inflate severity; every finding needs evidence and proportional impact.
   - Uses these questions to navigate the review:
     - Does it achieve the intended purpose?
     - Is it bug-free?
     - Can it be simplified?
     - Is it consistent with the documentation?
     - Are there design flaws or anti-patterns?
     - Are there design choices that make testing or validation unnecessarily difficult?
     - Anything else a senior reviewer would push back on? Use judgment.
   - Classifies each finding using judgment based on its evidence, impact, likelihood, task requirements, and risk of deferral. **Blocking** findings must be resolved before commit; **Non-blocking** findings are genuine issues that may reasonably be deferred; **Nits** are low-impact style or readability issues with an obvious local remedy. These are judgment categories, not mechanical issue-type rules.
   - Verifies claims with safe, bounded commands. The reviewer MUST assume that every gate required by `AGENTS.md` passed on the frozen target before dispatch. It SHOULD NOT rerun the complete gate suite, but MAY run focused tests or other bounded commands needed to investigate a specific finding. For every added, removed, or changed assertion, applies all applicable mutation requirements from `AGENTS.md` under **Test Guidelines**. Verifies supplied mutation evidence, produces any missing evidence only in the scratch copy, and records the commands and results under **Verification**.
   - Runs the scratch copy from its own root. The project is installed in editable mode, so confirm that a scratch-copy run imports `youtube_whisperer` from the scratch copy and not from the repository before trusting its results. `pyproject.toml` applies `--cov-fail-under=80` to every run, so a focused subset run reports `Required test coverage of 80% not reached` and exits non-zero even when every selected test passes; use `--no-cov` for focused runs and never read that exit code alone as a test failure. Tests run in random order under `pytest-randomly`, which prints its seed; reproduce an isolated failure with `--randomly-seed=<seed>` and label order-dependent results as such.
   - Keeps the repository read-only, cleans up only its recorded scratch artifacts and processes, reports that cleanup, and returns the report below.

4. **Validate and disposition findings.** The reviewer owns the triage and verdict. The main agent first compares repository status, recorded hashes, and the out-of-scope untracked path list against the step 1 snapshot; any unexplained repository change blocks the review. It then handles each finding according to its reviewer-assigned classification:

   - **Blocking:** The main agent MUST independently investigate and validate the claim and the premise and expected effect of any proposed remedy before accepting or implementing it. It MUST fix each validated Blocking finding. If a materially equivalent Blocking finding appears in two consecutive fresh reviews and the main agent still cannot validate it, stop and ask the user for direction.
   - **Nits:** The main agent SHOULD independently validate and fix each Nit. It MAY instead leave a Nit unfixed when the remedy is non-trivial, in which case it MUST surface the Nit to the user. Before implementing any Nit remedy, it MUST validate the claim and the remedy's premise and expected effect.
   - **Non-blocking:** The main agent MUST surface each finding directly to the user and NEED NOT independently investigate or validate it first.

   The main agent MUST NOT silently discard or reclassify a reviewer finding. For every finding, record **Validated**, **Could not validate**, or **Not independently validated**, with supporting evidence when validation was attempted. The user decides whether to fix, defer, or accept without change any surfaced Non-blocking finding or Nit. Before implementing a user-selected remedy, the main agent MUST independently validate the finding and the remedy's premise and expected effect.

## Report

Return this structure without rewritten code. Every finding MUST cite a path and, when possible, a line; write “None” for empty sections.

```markdown
## Adversarial Review Report
**Purpose:** ...
**Target:** ...
**Reviewer:** <model/tool; failure>
**Assumptions:** ...
**Verification:** <commands and results>

### Blocking
1. `path:line` — <defect>. Impact: ... Proposed remedy (optional): ...
### Non-blocking
...
### Nits
...
### Dismissed
<hypothesis and measured reason>
### Verdict
<No blocking findings | N blocking findings — fix and re-review | Review blocked — scratch environment or repository integrity>
```

After handling the report, the main agent appends a **Main-agent validation** section that records each finding as **Validated**, **Could not validate**, or **Not independently validated**, with supporting evidence when validation was attempted. This addendum does not alter the reviewer's triage or verdict.
