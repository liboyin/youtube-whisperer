This file is intended for AI agents.

# Ask Questions, Document Answers

Many design decisions in this project are undocumented. When something feels like an assumption, ask why it was designed that way. If an explanation is provided, update the documentation accordingly.

# Automated Tests + Static Analysis

Testing and static analysis tools have been configured for this project. After any code change, verify that:

1. `pytest` passes.
2. `mypy youtube_whisperer` reports no errors.
3. `ruff check` passes.

# Code Review

Review your own code changes after making code changes. If you noticed any issues or antipatterns, try to resolve them. If the issue or antipattern is related to the architecture or design of this project, please update ISSUES.md . Feel free to reorganise ISSUES.md to best suit the current state of the project.

# Isolated Workspaces

In a multi-agent scenario, each agent must use a Git worktree to set up an isolated workspace, preventing conflicts between agents working concurrently on the same repository.
