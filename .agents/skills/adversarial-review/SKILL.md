---
name: adversarial-review
description: Adversarial review and reviewer-owned triage of non-trivial code, test, or configuration changes. Use before commit when AGENTS.md requires independent review; return findings without changing the repository.
---

# Adversarial Review

Return a reviewer-triaged report without changing the repository. The reviewer MAY propose remedies but MUST NOT implement them. The main agent investigates and dispositions findings under step 4.

## Review Scope

Review each independently committed change against its complete target on its first assessment. Tightly coupled tasks delivered as one cohesive change MAY share a review covering all accepted boundaries and integration paths before commit. Previously reviewed tasks need a further group review only when integration introduces behavior or risks not covered by those reviews; record that coverage decision. For follow-ups, review the delta, affected call paths and invariants, and unresolved findings. If scope or design changes substantially, review the complete target again. Integrated review MUST reassess earlier conclusions against integration evidence.

Verified cosmetic follow-ups MAY reuse passed gates and verdicts. Verify that the change cannot affect behavior, test guarantees, build/configuration output, security, concurrency, state/data flow, or user-visible contracts; check relevant dependencies, environment, file modes and symlink targets remain unchanged. Terminal blank-line cleanup is a typical example; whitespace in strings or configuration and comments used as directives or runtime input are not automatically cosmetic. Run affected lint/format and diff checks, record the equivalence evidence and updated content fingerprints, and retain prior finding dispositions. When equivalence is uncertain, run full gates and review. Documentation-only changes and read-only assessments follow AGENTS' exemption.

## Reviewer Session

Reuse one Codex reviewer within a task or closely coupled group, retaining its own history for follow-ups. A fresh reviewer MAY be used for unrelated work, substantial redesign, or an unavailable prior reviewer; record the reason and transfer outstanding findings and dispositions. Create new reviewers without inherited main-agent history. Record agent/session identity, model and effort in the review record. Compaction or another user turn alone does not require replacement. The reviewer remains independent of implementation and MUST NOT edit the repository.

- **Codex:** initially use `spawn_agent` with `fork_turns: "none"`, `model: "gpt-6.1-sol"`, and `reasoning_effort: "high"`, unless the user selects other settings. Continue the recorded agent with `followup_task` unless replacement is warranted above.
- **Claude Code:** create the reviewer with `codex exec --dangerously-bypass-approvals-and-sandbox --model gpt-6.1-sol -c model_reasoning_effort="high" --json <review prompt>` and record the returned session ID. Continue it with `codex exec resume --dangerously-bypass-approvals-and-sandbox --model gpt-6.1-sol -c model_reasoning_effort="high" <SESSION_ID> <review prompt>`, retaining the selected settings. Use the explicit recorded ID rather than `--last`; add `--skip-git-repo-check` when needed outside a repository. CLI dispatch requires `command -v codex` and `codex login status` to succeed; report missing setup/authentication rather than installing a plugin.

[AGENTS.md](../../../AGENTS.md#scope-and-decisions) owns the devcontainer and Full Access assumptions. If the requested model or dispatch is unavailable, report the blocker and ask the user for direction; do not substitute or issue a verdict. Track each invocation through completion and capture its exit status and report before dispositioning findings.

## Procedure

1. **Gate, freeze, and snapshot.** Before dispatching the reviewer, the main agent MUST establish passing results for every gate required by `AGENTS.md` on the exact target state, by running it or verifying explicitly permitted reuse. If any gate fails, resolve the failure before formal review. Freeze repository edits and take a temporary integrity snapshot: `git status`, hashes/modes/symlink targets for dirty tracked and in-scope untracked files, out-of-scope untracked paths, and any relevant owned processes. Do not inspect or hash ignored untracked content. Start the compact [review record](#evidence-retention); the temporary integrity snapshot need not be retained after a successful comparison unless needed for evidence reuse or investigation.

2. **Dispatch the reviewer.** Ask the [recorded reviewer](#reviewer-session) to read the current skill, perform step 3 for the requested full or follow-up scope, and return the report; the main agent owns steps 1, 2 and 4.

   **Scratch copy.** Every dispatch MUST keep the repository read-only; the reviewer writes only outside it. Tests, mutation runs, commands executing application code, and other commands needing writable state MUST use a disposable scratch copy and delete it at exit. Source/diff reads and retained evidence output do not require a copy. Build the copy from the tracked target state plus the in-scope staged and unstaged changes, adding only the in-scope untracked files the dispatch names and never ignored or out-of-scope content. Preserve executable bits and recreate repository-relative symlinks so they resolve inside the scratch copy. Do not dereference links into the original repository or external paths; if a required copy cannot be created or a required target cannot be copied safely, return `Review blocked`. The reviewer is trusted here: step 1's snapshot and step 4's comparison detect accidental mutation, they are not a security boundary.

   A scratch copy does not itself satisfy AGENTS' test-ownership rules: focused tests and mutation runs also need test-owned paths, settings, and service doubles. Do not copy `.env`, browser profiles, media libraries, or model caches into the scratch copy, or run it against those resources through inherited configuration.

   **Execution provenance.** Verify that exercised application modules are imported from the scratch tree in each test process, including children, without changing the import lifecycle under test. Preserve the test bootstrap and owned settings/resources. A provenance or environment failure is invalid evidence, not a behavioral mutation kill. Read the [scratch-testing recipe](references/scratch-testing.md) when running tests or mutants.

   Pass only:

   - Repository path and exact target: dirty tree, commit, or range; for follow-ups, the last reviewed target and requested delta.
   - In-scope paths and any unrelated dirty paths to ignore.
   - Purpose of the change in a few sentences.
   - The retained record's location, including accepted boundaries and available evidence to read; the report destination if separate.

   Add undocumented constraints, accepted findings not to re-raise, or prior mutation evidence only when nonempty. Do not inline the diff, full conversation, architecture summaries available in the repository, suspected defects, or the main agent's conclusions.

   The reviewer MAY ask for further information when missing context could affect a finding or verdict. Reply with the minimum factual context and record the exchange under **Assumptions**.

3. **Review.** The reviewer:

   - Reads the current `AGENTS.md`, the complete requested diff, in-scope untracked files, and relevant source, tests, documentation, and configuration. Never reads ignored untracked content.
   - Takes a constructively adversarial stance: assume the change may be wrong and actively try to falsify it with counterexamples, boundary and failure cases, invariant violations, state transitions, tests that can pass for the wrong reason, and mutants. For this project, scrutinize Redis stream and consumer-group semantics, acknowledgement and dead-letter ordering, worker process and concurrency boundaries, filesystem and path handling, and external-service failure paths where relevant. Check intended behavior, correctness, simplicity, documentation, design and testability. Never manufacture findings, treat taste as a defect, or inflate severity; every finding needs evidence and proportional impact.
   - Classifies each finding using judgment based on its evidence, impact, likelihood, task requirements, and risk of deferral. **Blocking** findings must be resolved before commit; **Non-blocking** findings are genuine issues that may reasonably be deferred; **Nits** are low-impact style or readability issues with an obvious local remedy. These are judgment categories, not mechanical issue-type rules.
   - Verifies claims with safe, bounded commands. Rely on the main agent's passing gate results for the frozen target; do not repeat the complete suite without a specific concern. Run focused tests when needed. Apply AGENTS' targeted mutation requirements, including protection of removed/weakened coverage, and request additional mutation evidence where test protection is doubtful. Independently check supplied evidence using the [evidence rules](#evidence-retention); this does not require replaying every supplied mutant. Produce missing required evidence in scratch or return `Review blocked`. Count a mutation kill only when a relevant test fails for the protected invariant; collection, syntax, import and environment failures do not count. Record the invariant, mutant, command/seed, and behavioral outcome.
   - Keeps the repository read-only, preserves the required evidence record before cleaning up only its recorded disposable scratch artifacts and processes, reports that cleanup, and returns the report below.

4. **Validate and disposition findings.** The reviewer owns the triage and verdict. The main agent first compares repository status, recorded hashes, file modes, symlink targets, and the out-of-scope untracked path list against the step 1 snapshot; any unexplained repository change blocks the review. It then handles each finding according to its reviewer-assigned classification:

   - **Blocking:** The main agent MUST independently investigate and validate the claim and the premise and expected effect of any proposed remedy before accepting or implementing it. It MUST fix each validated Blocking finding. If a materially equivalent Blocking finding appears in two consecutive reviewer assessments and the main agent still cannot validate it, stop and ask the user for direction.
   - **Nits:** Independently validate and fix when practical and within scope; otherwise record a justified deferral.
   - **Non-blocking:** Independently investigate before implementing a remedy. The main agent MAY defer a finding with a reason and revisit trigger without waiting for user input, unless disposition materially changes scope, behavior, architecture, or accepted risk; those choices require user confirmation.

   Never silently discard or reclassify findings. Record each as **Validated**, **Could not validate**, or **Not independently validated**, with supporting evidence when investigated, plus its disposition. Report all Non-blocking findings and unfixed Nits to the user. Deferral is not permanent acceptance without change; honor existing user dispositions. Validate each remedy's premise and expected effect before implementing it. After non-trivial fixes, repeat AGENTS' gates and obtain an updated verdict; no unresolved Blocking finding may remain at completion.

## Report

Record purpose, target, reviewer, material assumptions, verification, limitations, and verdict without rewritten code. Every finding MUST cite a path and, when possible, a line. The following structure is available when useful; omit empty finding sections and dismissed hypotheses that do not explain a material decision. A clean report states that there are no findings. The report MAY be a section of the retained review record rather than a separate file.

```markdown
## Adversarial Review Report
**Purpose:** ...
**Target:** <candidate and full or follow-up scope; prior reviewed target when applicable>
**Reviewer:** <agent/session ID, model/effort, tool; failure>
**Assumptions:** ...
**Verification:** <commands and results>
**Limitations:** ...

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

After handling the report, the main agent appends a **Main-agent validation** section recording the integrity comparison and each finding's validation and disposition under step 4. When there are no findings, say so once; no empty disposition sections are needed. This addendum does not alter the reviewer's triage or verdict.

## Evidence Retention

Keep one compact [review record](references/review-record.md) outside disposable scratch and link it in the handoff. It records the boundary, target, reviewer, checks/results, findings/dispositions, integrity comparison result, and limitations. Include mutation evidence only when required or performed. Preserve accepted boundaries before removing their TODO entries. Retain enough candidate content to establish a follow-up diff when needed; a commit reference suffices for committed inputs, while uncommitted inputs need a patch or equivalent snapshot.

Assign one primary producer for required mutation evidence on each cohesive candidate; the reviewer may fill gaps or add probes. The reviewer MUST independently assess supplied evidence against the candidate: check the relevant source/test identity, exact mutant and protected assertion, execution command/seed, actual-import provenance, and behavioral outcome. Reliable matching evidence MAY be accepted without replay; the reviewer records what was checked. Rerun affected cases when those checks cannot establish validity, relevant inputs changed, or a concrete concern needs reproduction. Add a different probe when the supplied mutant does not distinguish the suspected failure. Independent review remains mandatory for non-trivial committed candidates; duplicate execution is not its definition.

Evidence reuse is optional. When reusing baselines, gates, mutation evidence, or verdicts, follow the template's additional provenance requirements; rerunning checks is always an alternative. Identical tested content MAY justify baseline reuse across changed commit metadata only when checks are metadata-independent. Cosmetic reuse follows [Review Scope](#review-scope); non-trivial fixes still require full gates and an updated verdict.

Preserve the record and its essential supporting files. Remove disposable scratch, owned processes and unnecessary logs after transferring essential evidence. User instructions govern retention or disposal. Never retain secrets, ignored content, host data, or copied external resources.
