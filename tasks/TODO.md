# TODO — Open work

This file holds the recommended order, the constraints that several tasks share, and the index of open tasks. [README.md](README.md) owns how tasks are recorded, bounded and closed.

- Read [AGENTS.md](../AGENTS.md), [DESIGN.md](../DESIGN.md) and the relevant operating instructions in the [project README](../README.md) before you accept an implementation task.
- A recorded task is not permission to combine unrelated changes or to redesign the service.
- For a group of related tasks, use the [grouped task execution skill](../.agents/skills/grouped-task-execution/SKILL.md).

## Recommended order

1. NB31 (Compose repetition) can land at any time. It changes no behavior.

These items are outside the sequence:

- The [transcription redesign handoff](../TRANSCRIPTION_REDESIGN.md) preserves the research behind DESIGN [D53](../DESIGN.md#d53). It is not an implementation assignment, and no backend or repository split is selected. Record bounded tasks when the user selects the platform experiments or later extraction work.
- The settled decisions bind every task. Examples are file naming ([D47](../DESIGN.md#d47)), playlist continuation ([D17](../DESIGN.md#d17)), caption errors ([D16](../DESIGN.md#d16)), and compatibility, resource ownership, settings lifetime and worker identity ([D18](../DESIGN.md#d18) to [D21](../DESIGN.md#d21)).
- Keep the existing Python entry points and all accepted product behavior. The translation interfaces that [D23](../DESIGN.md#d23) and [D24](../DESIGN.md#d24) removed are the only exception.

## Shared constraints

**Evidence.** An entry keeps the status of its original assessment. It does not claim current validation.

- **Validated** means that source inspection or a recorded command supported the finding at the cited revision.
- **Not independently validated** means that the finding came from a user request without separate evidence.
- Revalidate a finding before implementation. A historical line number locates code only at its assessment revision.
- [project-reviews.md](../project-reviews.md#evidence-provenance) holds the reviews of 2026-07 and 2026-09, with their revisions, environments, methods and limitations. Their gate results neither certify nor block today's tree.

**Checks that match the change.** AGENTS owns the gates and the review. Add the checks that match what changed:

- For a worker change, check queue and dead-letter behavior.
- For a downloader change, check extraction behavior.
- For an infrastructure change, run a Compose smoke test on the host. The devcontainer has no Docker daemon.
- Clean static analysis is not proof of correct concurrent behavior.

**Live services.** Keep checks against YouTube and Azure Speech out of the automated suite. Each such run needs the user's authorization, under [AGENTS Safety](../AGENTS.md#safety). Record no keys and no personal media paths.

## Open tasks

- [NB31](open/NB31.md) — Non-blocking, Low. Compose repeats the shared application-service configuration.
