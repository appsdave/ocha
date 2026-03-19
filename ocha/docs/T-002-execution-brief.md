# T-002 Execution Brief — Fix scrollbar glitch on UI refresh

**Coordinator:** S-002-01  
**Branch:** agent  
**Date:** 2026-03-19

---

## Goal (refined)

The operator reports that the scroll bar glitches when the UI refreshes.
After code review, the root causes are:

1. **AgentsPane full rebuild on every tick.** `AgentsPane.load()` calls
   `list_view.clear()` + re-append of all items whenever the snapshot
   changes. The snapshot includes `task.elapsed` (a formatted timer string)
   which changes every second for running tasks, so the list is torn down
   and rebuilt on every 2-second tick. This resets scroll position and
   causes visible flicker.

2. **OutputPane content replacement resets scroll.** `OutputPane.update_task()`
   replaces the entire `#output-content` Static text and then calls
   `scroll_end(animate=False)`. If the user has scrolled up to read earlier
   output, the pane jumps back to the bottom on every tick.

3. **No dirty-flag or diff-based update.** `refresh_from_state()` rebuilds
   all four widgets unconditionally; there is no mechanism to skip a widget
   if its data hasn't actually changed.

### Concrete fixes required

| Fix | File(s) | Description |
|-----|---------|-------------|
| **A — Stabilise AgentsPane snapshot** | `app/widgets.py` | Exclude the volatile `elapsed` field from the snapshot comparison so the list is only rebuilt when task count, status, or identity changes. Update elapsed text in-place via a targeted label refresh instead of tearing down the list. |
| **B — Diff-based OutputPane update** | `app/widgets.py` | Track the last rendered output lines. Only update `#output-content` when the line list actually changes. When new lines are appended, only call `scroll_end()` if the user was already at the bottom (i.e., not scrolled up). |
| **C — Guard refresh_from_state** | `app/app.py` | Add a lightweight generation counter or content hash so `refresh_from_state()` can short-circuit widgets that haven't changed. |
| **D — Reduce tick frequency** | `app/app.py` | Consider increasing the timer interval from 2 s to 3–5 s, or switching to event-driven refresh (post a custom `StateChanged` message when state actually mutates) instead of polling. |

---

## Relevant files

### Must-read for every downstream agent

| File | Why |
|------|-----|
| `app/widgets.py` | `AgentsPane.load()` (lines 61-70), `OutputPane.update_task()` (lines 111-137) — both glitch sources |
| `app/app.py` | `refresh_from_state()` (line 350), `_tick()` (line 287), `set_interval(2.0)` (line 284) — refresh orchestration |
| `app/state.py` | `AppState`, `OchaTask.elapsed` — data model and the volatile elapsed field |

### Secondary context

| File | Why |
|------|-----|
| `tests/test_app.py` | Existing app tests — must not break |
| `python-textual-rebuild.md` | Design doc for the Textual rebuild |
| `README.md` | Keybinding and UX intent |

---

## Safe partitioning for parallel worktrees

All agents share the `agent` branch. To avoid conflicts, respect these boundaries:

| Role | Owned directory | Scope |
|------|----------------|-------|
| **Coordinator** | `docs/` | This brief; context gathering only |
| **Lead** | `planning/` | Break fixes A–D into ordered builder sub-tasks |
| **Builder** | `app/` | Implement the fixes in `widgets.py` and `app.py` |
| **Reviewer** | `tests/` | Validate fixes, add regression tests for scroll stability |

The builder should avoid editing `docs/` or `planning/`. The reviewer should
avoid editing `app/` source — only `tests/` if new coverage is needed.

---

## Recommended sub-task breakdown (for the lead)

1. **Stabilise AgentsPane list refresh (Fix A)**
   - Remove `elapsed` from the `_snapshot()` fingerprint so the list isn't
     rebuilt every tick.
   - Instead, after the early-return, do a targeted in-place update of
     each item's label text (just the elapsed string) without clearing the
     list. This preserves scroll position and selection.
   - File: `app/widgets.py` (`AgentsPane._snapshot`, `AgentsPane.load`)

2. **Diff-based OutputPane refresh (Fix B)**
   - Store `_last_lines: list[str]` on `OutputPane`.
   - In `update_task()`, compare new lines to `_last_lines`. If identical,
     return early.
   - Only call `scroll_end()` when the user is already scrolled to the
     bottom (check `self.scroll_offset.y >= self.max_scroll_y - 1` or
     similar). This lets the user read history without being yanked to the
     bottom.
   - File: `app/widgets.py` (`OutputPane`)

3. **Guard refresh_from_state (Fix C)**
   - In `app.py`, add a `_state_generation: int` counter. Increment it
     only when state actually mutates (task added, status changed, output
     appended). Have `_tick()` compare generations and skip refresh if
     unchanged.
   - File: `app/app.py`

4. **Event-driven refresh option (Fix D)**
   - Replace or supplement `set_interval` polling with a custom Textual
     message `class StateChanged(Message)`. Post it from
     `_launch_task_from_prompt`, `_handle_kill`, `_advance_pipeline`, and
     the junie output streaming loop.
   - Keep a slower tick (5 s) only for elapsed-time cosmetic updates.
   - File: `app/app.py`

5. **Tests**
   - Add a test that `AgentsPane.load()` does not call `list_view.clear()`
     when only elapsed changes.
   - Add a test that `OutputPane.update_task()` does not call `scroll_end()`
     when the user has scrolled up and content is unchanged.
   - Files: `tests/test_app.py`

---

## Execution rules reminder

- Stay on the `agent` branch — no branch-per-agent.
- Each agent works in its own worktree under `.worktrees/`.
- Prefer changes inside the assigned owned directory.
- Summarize results so the TUI can surface a short workflow event.
