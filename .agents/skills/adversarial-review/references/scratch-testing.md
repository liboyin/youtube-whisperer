# Scratch Testing Recipe

Use this recipe when the [review procedure](../SKILL.md#procedure) requires scratch execution. It supplies examples, not a substitute for AGENTS' test-ownership rules.

Run fresh Python processes from the prepared scratch root using `python -m pytest`, with `PYTHONPATH` pointing to that root and `TMPDIR` plus pytest's `--basetemp` inside an owned scratch subdirectory. Preserve the copied `tests/conftest.py` configuration bootstrap. Add scratch-only provenance checks in the process exercising the code, after its configuration setup, without changing import timing or module absence protected by the tests; a separate `find_spec` probe does not certify the pytest process. For a focused API run whose tests normally import the app and do not test its import lifecycle, add the following hook only to the scratch copy of `tests/conftest.py`, after the existing configuration bootstrap. That location makes `Path(__file__).resolve().parents[1]` the scratch root. Preserve existing hooks and imports; do not use this eager-import example for a full suite containing import-lifecycle tests:

```python
from pathlib import Path

import pytest


def pytest_sessionstart(session):
    """Reject pytest runs that import the API outside the owned scratch tree."""
    import youtube_whisperer.api.app as testee

    scratch_root = Path(__file__).resolve().parents[1]
    if not Path(testee.__file__).resolve().is_relative_to(scratch_root):
        raise pytest.UsageError("Application import escaped the scratch tree")
```

Adapt the checks to the application modules exercised or mutated and preserve existing hooks. For lazy-import or import-lifecycle tests, inspect the actual module in `sys.modules` after the test-controlled import instead of preloading it for verification; modules expected to remain absent MUST remain absent. For test-spawned child processes, add equivalent scratch-only location checks inside each child after its own configuration setup and controlled imports. A parent pytest check does not certify a child's imports. From the scratch root, a focused API run is:

```bash
mkdir -p owned-temp
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/owned-temp" python -m pytest tests/api/test_app.py --no-cov --basetemp="$PWD/owned-temp/pytest"
```

A run failing the import check is invalid evidence, rather than a surviving or killed mutant. Restore the candidate source before each mutant, and save required evidence outside disposable scratch before cleanup. `PYTHONPATH` and owned temporary paths do not replace the test bootstrap's settings isolation or service doubles.

The focused command uses `--no-cov` because the repository's default pytest coverage threshold applies to the whole application. Preserve pytest-randomly's reported seed when reproducing a failure, and identify order-dependent results.
