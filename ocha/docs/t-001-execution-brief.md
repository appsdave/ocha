# T-001 Execution Brief — Ship prompt-based task creation

> Produced by the **coordinator** role (session S-001-01).

---

## Goal (refined)

Ocha currently accepts task descriptions only as inline strings — either typed
into the TUI `NewTaskOverlay` TextArea or passed as a positional CLI argument to
`ocha launch "…"`.  The operator has asked us to **ship prompt-based task
creation**: the ability to create a task from a prompt file (e.g.
`prompts/refactor-auth.md`) or a named template, so that repeatable,
version-controlled task descriptions can drive the orchestration pipeline.  This
means adding a `--prompt-file` / `-f` flag to the CLI, a file-picker or
paste-from-file flow in the TUI overlay, and the plumbing in the orchestrator to
accept a `Path` source alongside the existing raw-string path.

---

## Relevant files

| File | Role | Action |
|---|---|---|
| `app/cli.py` | Builder | Edit — add `--prompt-file` flag to the `launch` sub-command and wire it into `build_launch_specs` |
| `app/orchestrator.py` | Builder | Edit — add `load_prompt_file(path) -> str` helper; update `build_launch_specs` and `launch_task` to accept an optional `prompt_file: Path` parameter |
| `app/app.py` (`NewTaskOverlay`) | Builder | Edit — extend the overlay to accept a file path (paste or type) in addition to inline text |
| `app/state.py` | Builder | Read — no changes expected; `OchaTask.user_task` already stores the resolved string |
| `app/roles/coordinator.md` | Coordinator | Read-only reference |
| `tests/test_orchestrator.py` | Reviewer | Edit — add tests for `load_prompt_file`, file-based `build_launch_specs`, and error cases |
| `tests/test_cli.py` | Reviewer | Edit — add CLI integration tests for `--prompt-file` |
| `tests/test_app.py` | Reviewer | Edit — add TUI overlay tests for the file-path input |
| `pyproject.toml` | Lead | Read — verify no new dependencies are needed |
| `docs/` | Coordinator | Write — this brief |

---

## Recommended changes

### Phase 1 — Orchestrator plumbing (Builder, `app/`)

1. **`app/orchestrator.py`** — Add a `load_prompt_file(path: Path) -> str`
   function that reads a `.md` or `.txt` file, validates it is non-empty and
   within the `MAX_PROMPT_LENGTH` guard (100 KB, matching the TUI limit), and
   returns the raw text.
2. **`app/orchestrator.py`** — Give `build_launch_specs()` and `launch_task()`
   an optional `prompt_file: Path | None = None` keyword.  When provided, call
   `load_prompt_file` to resolve `user_task` before the rest of the pipeline
   runs.
3. **`app/orchestrator.py`** — In `persist_task_prompt()`, if a file source was
   used, record the original path in a sidecar `prompt_source.txt` for audit.

### Phase 2 — CLI surface (Builder, `app/`)

4. **`app/cli.py`** — Add `--prompt-file` / `-f` to the `launch` sub-parser.
   Make `task` positional argument optional when `--prompt-file` is supplied.
   Validate mutual exclusivity (cannot supply both inline task and file).
5. **`app/cli.py`** — Pass the resolved `prompt_file` through to
   `build_launch_specs`.

### Phase 3 — TUI surface (Builder, `app/`)

6. **`app/app.py` (`NewTaskOverlay`)** — Add a small `Input` widget above the
   TextArea labelled "prompt file (optional)".  When the overlay is submitted,
   if the input contains a path, load it via `load_prompt_file`; otherwise fall
   through to the existing TextArea flow.
7. Ensure the overlay shows a clear validation error if the file doesn't exist
   or exceeds the size limit.

### Phase 4 — Tests & review (Reviewer, `tests/`)

8. **`tests/test_orchestrator.py`** — Unit tests for `load_prompt_file`:
   valid file, missing file (`FileNotFoundError`), empty file (`ValueError`),
   oversized file (`ValueError`).
9. **`tests/test_orchestrator.py`** — Test that `build_launch_specs` with
   `prompt_file` produces identical specs to the inline-string path.
10. **`tests/test_cli.py`** — CLI integration: `ocha launch -f prompt.md`
    succeeds; mutual-exclusivity error when both positional and `-f` are given.
11. **`tests/test_app.py`** — TUI test: overlay dismisses with file content
    when a valid path is entered.

---

## Safe partitioning

| Owned directory | Role | Notes |
|---|---|---|
| `docs/` | Coordinator | This brief; no code changes |
| `planning/` | Lead | Detailed task plan derived from this brief |
| `app/` | Builder | All production code changes (orchestrator, cli, app) |
| `tests/` | Reviewer | All new and updated test files |

All workers stay on the shared `agent` branch.  The builder owns `app/` and the
reviewer owns `tests/` — these do not overlap, so no merge conflicts are
expected.  The lead writes a plan to `planning/` which the builder reads but
does not edit.

---

*Coordinator session S-001-01 complete.*
