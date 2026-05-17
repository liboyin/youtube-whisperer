This file is intended for AI agents.

# Meta Guidelines

- If not running in a Docker container, stop and confirm with the user before continuing.
- State assumptions explicitly. When you notice ambiguity (e.g. two conflicting patterns, or a design choice with no stated rationale), confirm with the user before continuing.
- Prefer spawning subagents to keep the main context window clean.
- Before considering a task done, re-check that all instructions in this file are followed.

# Documentation Guidelines

- `README.md` describes project architecture, dataflow, design decisions, and assumptions for both humans and AI agents. It is the WHY document and must not be mixed with HOW content.
- New or modified functions/methods in non-test scripts require Google-style docstrings; unit test functions require a one-line docstring.

# Implementation Guidelines

- Prefer the simplest implementation, even if it violates SOLID principles. No feature beyond what was asked.
- Use up-to-date features from languages, libraries, and frameworks.
- Break changes into small, functionally isolated chunks; commit as you go.
- Commit messages must follow this template:

```
<Your name: Claude/Codex/Gemini/...>: <one-line summary>

<One paragraph describing the change in detail. If more than one paragraph is necessary, the change can probably be broken down.>
```

# Unit Tests + Static Analysis

Tests must encode WHY behavior matters, not just WHAT it does. A test that does not fail when business logic changes is wrong.

After any code change, all of the following must pass:

```
pytest
mypy youtube_whisperer
ruff check .
```

Coverage must be at least 85% overall across statements, branches, functions, and lines.

Unit tests run in random order (`pytest-randomly`); do not rely on execution order.

When writing unit tests:

- Order test functions to match the order their corresponding functions appear in the source file.
- Import the module under test with `import my_module as testee`. Call functions as `testee.function_name`. Mock attributes as `patch.object(testee, 'attribute', ...)`.

After modifying a non-test script, run `mypy` and ensure no new errors are reported on changed lines. Note that there are existing `mypy` errors in this project.

# Review Guidelines

Review your own changes before committing:

- Does it achieve the intended purpose?
- Is it bug-free?
- Are there design flaws or anti-patterns?
- Can it be simplified?
- Anything else a senior reviewer would push back on? (Use judgment)

Fix trivial issues. For others, stop and confirm with the user.
