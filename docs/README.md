# ocha — Documentation

This directory contains the long-lived documentation for the ocha project: architecture notes, workflow behavior, and operational design references.

## Core references

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Current application structure, including notifications UI, worktree lifecycle helpers, task artifact model, pipeline advancement flow, CLI surface, and runtime behavior |
| [merge-conflict-prevention.md](merge-conflict-prevention.md) | Shared-branch conflict-avoidance model: lock registry, execution grouping, scope checks, and role ownership |
| [`../ocha/README.md`](../ocha/README.md) | Operator-facing install guide, command reference, updated project layout, orchestration pipeline, and shared-branch git workflow |
| [`../ocha/junie-headless-sessions.md`](../ocha/junie-headless-sessions.md) | Headless Junie session design notes and runtime constraints |
| [`../ocha/python-textual-rebuild.md`](../ocha/python-textual-rebuild.md) | Background notes for the Python/Textual rebuild |

## Task artifact references

Task-specific briefs exist as supporting artifacts, but they should not be treated as the source of truth for the current product behavior:

| Brief | Notes |
|-------|-------|
| [T-001-highlight-active-focus-brief.md](T-001-highlight-active-focus-brief.md) | Historical coordinator brief retained for reference |
| [`../ocha/docs/t-001-execution-brief.md`](../ocha/docs/t-001-execution-brief.md) | Package-local execution brief produced for the prompt-based task-creation work |

## Quick links

- **Role prompts**: [`ocha/app/roles/`](../ocha/app/roles/) — markdown prompts for coordinator, lead, builder, reviewer
- **Task artifact layout**: [`../ocha/README.md#task-creation-examples`](../ocha/README.md#task-creation-examples) — `.ocha/tasks/T-*/prompt.md`, `status.json`, and per-session `prompt.md` / `session.json`
- **Shared branch model**: [`../ocha/README.md#git-workflow`](../ocha/README.md#git-workflow) — all workers stay on `agent`
