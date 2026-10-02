# Review Record

Use this compact template for the [review procedure](../SKILL.md#procedure). References to retained artifacts are sufficient; do not duplicate their contents. Omit conditional sections when they do not apply.

- **Boundary:** intent, dependencies, non-goals, acceptance criteria; link or preserve the accepted task/group boundary.
- **Target:** starting and candidate revisions/range, in-scope paths and uncommitted inputs; full or follow-up scope and prior target when applicable.
- **Reviewer:** agent/session ID, model/effort; replacement reason and transferred findings when applicable.
- **Checks:** commands, results, relevant non-secret environment summary, and baseline selection rationale. Include the integration-coverage decision when deciding whether a further group review is needed.
- **Findings:** reviewer report and verdict, main-agent validation and dispositions, reasons/revisit triggers for deferrals, and any user decisions.
- **Integrity and cleanup:** snapshot comparison outcome, cleanup performed, retained artifact locations, and material limitations.

## Mutation evidence, when required or performed

For each protected invariant, record the mutant definition, relevant test, exact command/seed, and behavioral failure. Explain why the chosen mutation probes the risk; no category checklist or assertion-by-assertion inventory is required. Multiple assertions may share evidence. For removed/weakened coverage, identify the remaining test that still rejects the broken behavior. Report invalid runs separately from behavioral failures.

## Additional provenance for evidence reuse

Record the original tested revision, commands/results and evidence location. Compare relevant implementation, tests, call-path dependencies, configuration, file modes, symlink targets and environment. Include in-scope untracked inputs; never read ignored content or secrets to construct provenance. Record tested-input fingerprints and the non-secret environment evidence establishing equivalence, including tool/dependency versions where relevant. Changed or unknown relevant inputs invalidate reuse; rerun the affected checks instead. Revision-sensitive checks also require a new run when metadata changes.

For cosmetic gate/verdict reuse, explain why the delta cannot affect the contracts listed in the skill, record affected lint/format and diff checks and updated fingerprints, and preserve all prior finding dispositions. Reuse does not waive review after non-trivial fixes.

Retain reconstructible candidates when needed for reuse or follow-up comparison: revisions plus patches for uncommitted inputs, or equivalent snapshots. Fingerprints identify content but cannot reconstruct it. Keep referenced evidence outside disposable scratch; detailed logs may be discarded once definitions, outcomes and provenance are sufficient.
