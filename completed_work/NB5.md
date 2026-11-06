# NB5 — Lock-file regeneration is a side effect of creating the container

## Origin

Inherited from legacy finding 26 and validated at `98c4518`: `.devcontainer/postCreateCommand.sh` ran `pip freeze` into `requirements.txt` on every devcontainer create, so the lock changed on a plain rebuild instead of when dependencies changed. The mechanism for making regeneration deliberate was left open for the user; an `update_lock.sh` script had been proposed in `PLAN.md` and was rejected.

## Disposition

Resolved by [NB46](NB46.md), after the user chose uv as the mechanism on 2026-11-06 ([D50](../DESIGN.md#d50)). The hook no longer writes any lock: it runs `uv sync --locked`, which fails rather than rewriting when `uv.lock` is stale. README's "Updating dependencies" section documents the deliberate refresh with `uv lock --upgrade`, `--upgrade-package` and `uv add`. Validation, review and limitations are shared and recorded in [NB46](NB46.md#validation-and-provenance); the acceptance check that a devcontainer rebuild leaves the repository unmodified is among NB46's host-side limitations.
