This file is intended for AI agents.

# Ask Questions, Document Answers

Many design decisions in this project are undocumented. When something feels like an assumption, ask why it was designed that way. If an explanation is provided, update the documentation accordingly.

# Unit Tests + Static Analysis

After any code change, verify all of the following pass before considering the task done:

```
pytest
ruff check .
```

Coverage must be at least 85% for each source file and for the overall project.

When writing unit tests:

- Order test functions to match the order their corresponding functions appear in the source file.
- Import the module under test as `testee`. Call functions as `testee.function_name`. Mock attributes as `patch.object(testee, 'attribute', ...)`.

# Code Review

Review your own code changes after making code changes. If you noticed any issues or antipatterns, try to resolve them. If the issue or antipattern is related to the architecture or design of this project, please update ISSUES.md . Feel free to reorganise ISSUES.md to best suit the current state of the project.

# Isolated Workspaces

In a multi-agent scenario, each agent must use a Git worktree to set up an isolated workspace, preventing conflicts between agents working concurrently on the same repository.
