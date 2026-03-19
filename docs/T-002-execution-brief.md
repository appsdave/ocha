# T-002 Execution Brief

> Coordinator output for task T-002.  
> Generated: 2026-03-19 21:34  
> Branch: `agent`

## Operator request (paraphrased)

Fix UI glitching in the TUI, ensure the `agent` branch exists and is used for all work, and update markdown documentation to reflect the branch change.

---

## 1 — UI glitching: root causes identified

### 1a. Full list-view rebuild every 2 seconds (primary glitch)

**File:** `ocha/app/widgets.py` → `AgentsPane.load()` (line 52-57)  
**File:** `ocha/app/app.py` → `_tick()` (line 287-289) and `refresh_from_state()` (line 348-356)

Every 2-second tick calls `refresh_from_state()`, which calls `AgentsPane.load()`. That method does:

```python
list_view.clear()          # destroys all ListItems
for i, task in enumerate(state.tasks):
    list_view.append(...)  # rebuilds from scratch
list_view.index = ...      # resets highlight
```

This causes visible flicker because Textual tears down and rebuilds the entire DOM subtree of the sidebar on every tick. It also resets scroll position and can cause the highlight bar to jump.

**Fix approach:** Only rebuild when the task list actually changes (compare task IDs + statuses). For elapsed-timer updates, update the existing `Static` widget text in place rather than destroying/recreating `ListItem` nodes. Alternatively, skip the sidebar rebuild entirely when only the timer text changed — timers are cosmetic.

### 1b. TaskHeader and OutputPane rebuilt on every tick too

`refresh_from_state()` also calls `TaskHeader.update_task()` and `OutputPane.update_task()` unconditionally. The `OutputPane.update_task()` calls `self.scroll_end(animate=False)` every time, which forces the output pane to jump to the bottom even if the user scrolled up to read earlier output.

**Fix approach:** Only call `scroll_end` when new lines have actually been appended. Track `len(lines)` or a generation counter and skip the scroll when content hasn't changed.

### 1c. Minor: highlight CSS uses background same as default

In `app.py` CSS (lines 98-111), both `ListView > ListItem` and `ListView > ListItem.--highlight` share `background: #282828`. The only visual difference is a left border change. This makes the highlight almost invisible when the list rebuilds and the border briefly disappears.

**Fix approach (optional):** Use a slightly different background for `--highlight`, e.g. `#3c3836`, to make selection more visible during redraws.

---

## 2 — Branch model: `ocha` vs `agent` mismatch

### 2a. app.py uses wrong branch name

**File:** `ocha/app/app.py`, line 19  
```python
OCHA_BRANCH = "ocha"
```

But `ocha/app/orchestrator.py`, line 11 says:
```python
SHARED_BRANCH = "agent"
```

The TUI's `_ensure_ocha_branch()` creates/checks out a branch called `ocha`, while the orchestrator tells every worker they're on `agent`. These must agree.

**Fix:** Change `OCHA_BRANCH` in `app.py` to `"agent"` (or import `SHARED_BRANCH` from orchestrator). Update `_ensure_ocha_branch()` references accordingly.

### 2b. _post_pipeline_git_flow creates per-task branches

**File:** `ocha/app/app.py`, lines 594-663

After all workers finish, `_post_pipeline_git_flow` creates a branch `ocha/<task-id>`, commits, pushes, attempts a PR against `main`, then checks out `main`. This violates the shared-branch model described in the docs and orchestrator.

**Fix:** The post-pipeline flow should:
1. Stay on the `agent` branch (not create `ocha/<task-id>`)
2. Stage and commit on `agent`
3. Push `agent` to origin
4. Not switch back to `main`
5. PR creation can target `main` from `agent` if desired

### 2c. Git branch creation

The `agent` branch does not currently exist (only `main` and `ocha` exist). The fix in 2a will cause `_ensure_ocha_branch()` to create it automatically on next app launch.

---

## 3 — Markdown documentation updates needed

The following files reference the old branch name or contain stale information:

| File | What to update |
|------|---------------|
| `ocha/README.md` | References to branch model — ensure `agent` is documented as the shared branch |
| `ocha/python-textual-rebuild.md` | Check for any branch references |
| `ocha/junie-headless-sessions.md` | Check for any branch references |
| `ocha/app/roles/coordinator.md` | Already says `agent` — verify |
| `ocha/app/roles/lead.md` | Already says `agent` — verify |
| `ocha/app/roles/builder.md` | Already says `agent` — verify |
| `ocha/app/roles/reviewer.md` | Already says `agent` — verify |

---

## 4 — Recommended work partitioning

All work stays on the shared `agent` branch. Partition by directory to avoid conflicts:

| Role | Scope | Key files |
|------|-------|-----------|
| **Builder** | Fix UI glitching + branch constant | `ocha/app/app.py`, `ocha/app/widgets.py` |
| **Builder** | (same session) Fix `_post_pipeline_git_flow` | `ocha/app/app.py` lines 594-663 |
| **Reviewer** | Verify fixes, run tests | `ocha/tests/test_app.py`, `ocha/tests/test_orchestrator.py` |
| **Lead** | Update markdown docs for branch rename | `ocha/README.md`, `ocha/python-textual-rebuild.md`, `ocha/junie-headless-sessions.md` |

No overlapping file edits between roles. Builder owns `app/`, Lead owns docs, Reviewer reads everything.

---

## 5 — Success criteria

- [ ] TUI sidebar does not flicker on 2-second refresh when task list is unchanged
- [ ] Output pane does not auto-scroll when no new content arrived
- [ ] `OCHA_BRANCH` in app.py matches `SHARED_BRANCH` in orchestrator.py (both `"agent"`)
- [ ] `_post_pipeline_git_flow` commits and pushes on `agent`, does not create per-task branches
- [ ] All markdown files reference `agent` as the shared branch
- [ ] Existing tests pass (`pytest ocha/tests/`)

---

## 6 — TUI event summary

```
[coordinator] T-002 brief ready — 3 UI glitch causes identified, branch mismatch ocha→agent found, doc update scope mapped. Builder: app.py + widgets.py. Lead: markdown docs. Reviewer: test suite.
```
