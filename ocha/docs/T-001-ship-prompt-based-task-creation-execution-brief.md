# T-001 Execution Brief — Ship Prompt-Based Task Creation

> Produced by: coordinator · session S-001-01 · branch `agent`

---

## Goal (refined)

The operator asked to **ship prompt-based task creation**. The core pipeline already exists end-to-end: `NewTaskOverlay` (TUI modal) captures a free-text prompt, `launch_task()` in `orchestrator.py` fans it out to four role-backed `JunieLaunchSpec` workers (coordinator → lead → builder → reviewer), `persist_task_prompt()` writes the prompt to `.ocha/tasks/<id>/prompt.md`, and `_spawn_junie_workers()` / `_advance_pipeline()` execute the headless Junie sessions sequentially. What remains to "ship" this feature is: (1) harden the CLI path so `ocha launch` can accept a prompt from a file or stdin (not just a positional arg), (2) add integration-level tests that cover the full creation→persistence→pipeline-advance flow including edge cases (empty prompt, oversized prompt, multiline), (3) ensure the `NewTaskOverlay` validates and surfaces errors correctly, and (4) add user-facing documentation describing how to create a task via both the TUI and CLI.

---

## Relevant files

| File | Role | Action |
|---|---|---|
| `app/orchestrator.py` | builder | Read + edit — add `load_task_from_file()` helper; harden `summarize_task` |
| `app/cli.py` | builder | Edit — extend `launch` subcommand to accept `--file` / stdin |
| `app/app.py` | builder | Read + minor edit — `NewTaskOverlay._submit` validation is already solid; add character-count display |
| `app/state.py` | builder | Read-only — no changes expected |
| `app/widgets.py` | reviewer | Read-only — verify pane refresh after new task |
| `app/roles/coordinator.md` | lead | Read-only — no changes |
| `app/roles/lead.md` | lead | Read-only — no changes |
| `app/roles/builder.md` | lead | Read-only — no changes |
| `app/roles/reviewer.md` | lead | Read-only — no changes |
| `tests/test_orchestrator.py` | builder | Edit — add prompt-from-file and edge-case tests |
| `tests/test_cli.py` | builder | Edit — add `launch --file` and stdin tests |
| `tests/test_app.py` | builder | Edit — add `NewTaskOverlay` unit tests |
| `pyproject.toml` | reviewer | Read-only — verify entry-points are correct |
| `README.md` | lead | Edit — add "Creating a task" usage section |
| `.ocha/tasks/` | — | Runtime artifact directory, read-only reference |

---

## Recommended changes

### Phase 1 — CLI prompt input (builder, `app/`)

1. **`app/cli.py`**: Add `--file` option to the `launch` subcommand that reads a prompt from a file path. When `--file -` is passed, read from stdin. Keep the existing positional `task` argument as the default path.
2. **`app/orchestrator.py`**: Extract a small `load_prompt(source: str | Path) -> str` utility that normalises the prompt (strip, validate length ≤ 100 KB, reject empty). Use it from both `cli.py` and the TUI overlay.
3. **`tests/test_cli.py`**: Add tests for `launch --file <path>`, `launch --file -` (stdin mock), missing file, and empty-file error.
4. **`tests/test_orchestrator.py`**: Add tests for `load_prompt` edge cases — empty, whitespace-only, oversized, binary content.

### Phase 2 — TUI hardening (builder, `app/`)

5. **`app/app.py`** (`NewTaskOverlay`): Reuse the shared `load_prompt` validator so TUI and CLI enforce identical constraints. Show a live character count in the hint bar.
6. **`tests/test_app.py`**: Add focused `NewTaskOverlay` tests — submit with empty prompt, submit with oversized prompt, successful submit returns stripped text, escape dismisses with `None`.

### Phase 3 — Documentation (lead, `README.md` / `docs/`)

7. **`README.md`**: Add a "Creating a task" section with examples for both `ocha launch "prompt"` and `ocha launch --file prompt.md`.
8. **`docs/`**: Add a short `prompt-task-creation.md` guide covering: prompt format tips, size limits, how the prompt flows through the four roles, and where the prompt is persisted.

### Phase 4 — Review (reviewer, `app/`)

9. Verify all new and existing tests pass (`python -m pytest`).
10. Confirm the CLI `launch` path and TUI `NewTaskOverlay` both persist the prompt to `.ocha/tasks/`.
11. Check that `_advance_pipeline` correctly injects upstream output when the coordinator finishes.

---

## Safe partitioning

| Owned directory | Role | Scope |
|---|---|---|
| `docs/` | coordinator | This brief; `prompt-task-creation.md` guide |
| `README.md` + `docs/` | lead | Usage documentation, task plan |
| `app/` + `tests/` | builder | All code and test changes (phases 1–2) |
| `app/` (read-only) | reviewer | Review code changes, run tests (phase 4) |

All roles stay on the shared `agent` branch. No worktree conflicts expected because:
- **coordinator** only writes to `docs/`
- **lead** writes to `README.md` and `docs/` (non-overlapping files)
- **builder** writes exclusively to `app/` and `tests/`
- **reviewer** reads only, writes review verdicts to `docs/`

---

*Brief produced by coordinator session S-001-01 for task T-001.*
