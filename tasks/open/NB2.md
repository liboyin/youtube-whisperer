# NB2 — Ruff runs with its default rule set

**Priority:** Non-blocking. Its investigation gate comes first.

**Evidence:** validated at `98c4518`, where no `[tool.ruff]` configuration existed. Only the default `E4`, `E7`, `E9` and `F` rules were active. Nothing enforced line length, import order, docstring style or common bug patterns. AGENTS requires narrow, justified lint exceptions, but almost nothing produced one.

**Revalidation, 2026-11-23:** Ruff 0.17.6's default rule set is wider than that evidence states. It also includes EXE001, PLW1510 and D419, which T2 (review tooling) had to satisfy. youtube-collector selects `E`, `W`, `F`, `I`, `B`, `UP` and `D`, with the Google convention. A trial of that docstring selection here found 103 findings in the package and the skill scripts, and 150 with the tests.

- **Paths:** [pyproject.toml](../../pyproject.toml).
- **Investigation gate:** inventory the violations that an expanded selection produces before you choose the rule set. The task does not authorize a wholesale reformat. The investigation can expose new decisions. It does not authorize guessing them.
- **Direction:** after the inventory, select a broader rule set. pydocstyle with the Google convention would enforce the docstring rule that AGENTS states in prose. When it does, delete that prose rule.
- **Acceptance:** `ruff check .` passes under the expanded selection, and every `noqa` carries the rationale that AGENTS requires.
- **Non-goals:** restructuring code beyond what the selected rules demand.
- **Inventory, 2026-09-12:** the source still uses `Any` in the language-schema hooks, the playlist metadata, the Azure callbacks and the model parameters. Several source classes lack docstrings. Tests still patch by string, for example `tests/transcriber/test_model_parameters.py:7`, and use other import forms.
- **Scope of the inventory:** separate these items from runtime defects. Distinguish the rules that Ruff can enforce from typing work and test-structure work. Do not claim that a broader selection alone resolves them.
