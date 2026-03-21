# ocha — Documentation

This directory contains design documentation and execution briefs for the ocha project.

## Contents

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Internal architecture: module graph, data model, request flows, widget hierarchy, git operations, CLI surface, and structured logging |
| [merge-conflict-prevention.md](merge-conflict-prevention.md) | File-ownership lock system that prevents merge conflicts between concurrent workers |
| [`../ocha/README.md#task-creation-examples`](../ocha/README.md#task-creation-examples) | Current task artifact layout, including `.ocha/tasks/T-*/sessions/S-*/prompt.md` and `session.json` |

## Task briefs

Task-specific execution briefs are created by the coordinator role during each task pipeline:

| Brief | Task |
|-------|------|
| [T-001-highlight-active-focus-brief.md](T-001-highlight-active-focus-brief.md) | Better highlighting of the currently focused TUI pane |

## Quick links

- **Main README**: [`ocha/README.md`](../ocha/README.md) — install instructions, CLI usage, orchestration pipeline, git workflow
- **Role prompts**: [`ocha/app/roles/`](../ocha/app/roles/) — markdown prompts for coordinator, lead, builder, reviewer
- **Design notes**: [`ocha/python-textual-rebuild.md`](../ocha/python-textual-rebuild.md), [`ocha/junie-headless-sessions.md`](../ocha/junie-headless-sessions.md)
