# T-002 Execution Plan — Fix scrollbar glitch on UI refresh

> Lead: planning/T-002-plan.md
> Date: 2026-03-19
> Branch: `agent`
> Source: docs/T-002-execution-brief.md (coordinator output)

---

## Problem summary

The TUI glitches on periodic refresh: the sidebar list flickers (full
teardown/rebuild every 2 s), the output pane yanks scroll position to
the bottom even when the user scrolled up to read history, and
`refresh_from_state()` unconditionally rebuilds all widgets with no
change detection.

---

## Phase 0 — Branch bootstrap (coordinator)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 0.1 | Verify `agent` branch is active | coordinator | `git rev-parse --abbrev-ref HEAD` must return `agent`. Already handled by `_ensure_ocha_branch()` and `OCHA_BRANCH = "agent"`. |

**Gate:** `agent` branch confirmed before builder work starts.

---

## Phase 1 — Builder: Fix UI refresh glitches (all edits in `ocha/app/`)

No other role touches these files.

### 1.1 — Stabilise AgentsPane list refresh (Fix A)

**File:** `ocha/app/widgets.py` — `AgentsPane._snapshot()` and `AgentsPane.load()`

- Remove the volatile `elapsed` field from `_snapshot()` so the list is
  only rebuilt when task count, IDs, or statuses change.
- After the early-return (snapshot match), do a **targeted in-place
  update** of each item's label text to refresh elapsed strings without
  calling `clear()` + full rebuild. This preserves scroll position and
  selection highlight.

### 1.2 — Diff-based OutputPane refresh (Fix B)

**File:** `ocha/app/widgets.py` — `OutputPane`

- Add a `_last_lines: list[str]` attribute to track previously rendered
  output lines.
- In `update_task()`, compare the new lines to `_last_lines`. If
  identical, return early — do not replace `#output-content` text.
- Only call `scroll_end()` when the user is already at the bottom
  (check `self.scroll_offset.y >= self.max_scroll_y - 1` or equivalent).
  This prevents yanking the user away from history they are reading.
- When new lines *are* appended and the user *was* at the bottom,
  auto-scroll as before.

### 1.3 — Guard refresh_from_state with generation counter (Fix C)

**File:** `ocha/app/app.py` — `OchaApp`

- Add a `_state_generation: int` counter on `OchaApp.__init__`.
- Increment it only when state actually mutates: task added
  (`_launch_task_from_prompt`), task killed (`_handle_kill`), worker
  status changed (`_advance_pipeline`), or new output streamed
  (`_run_junie_for_worker`).
- In `_tick()`, compare generations and skip `refresh_from_state()` if
  unchanged. Always do a lightweight elapsed-time-only update for
  cosmetic timers.

### 1.4 — Event-driven refresh with slower poll fallback (Fix D)

**File:** `ocha/app/app.py`

- Define a custom Textual message `class StateChanged(Message)`.
- Post `StateChanged` from `_launch_task_from_prompt`, `_handle_kill`,
  `_advance_pipeline`, and the junie output streaming loop.
- Handle `StateChanged` to trigger `refresh_from_state()`.
- Change `set_interval` from 2 s to 5 s; the tick now only refreshes
  elapsed-time display (the lightweight path from 1.3), not full state.

**Gate:** `pytest ocha/tests/` passes with all Phase 1 changes applied.

---

## Phase 2 — Reviewer: Validation & regression tests (edits in `ocha/tests/`)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 2.1 | Run full test suite | reviewer | `pytest ocha/tests/ -v` — all existing tests must pass. |
| 2.2 | Add AgentsPane stability test | reviewer | Verify `AgentsPane.load()` does NOT call `list_view.clear()` when only `elapsed` changes (snapshot stable). |
| 2.3 | Add OutputPane scroll test | reviewer | Verify `OutputPane.update_task()` does NOT call `scroll_end()` when content is unchanged or user has scrolled up. |
| 2.4 | Add generation-counter test | reviewer | Verify `_tick()` skips `refresh_from_state()` when `_state_generation` is unchanged. |
| 2.5 | Verify no regressions | reviewer | Manual checklist: sidebar selection preserved across ticks, output pane shows new content, scroll bar stable. |

---

## Phase 3 — Sync: Commit & push

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 3.1 | Stage all changes | coordinator | `git add -A` on `agent` branch. |
| 3.2 | Commit | coordinator | `git commit -m "T-002: fix UI scroll/refresh glitch — diff-based updates + event-driven refresh"` |
| 3.3 | Push | coordinator | `git push -u origin agent` |

---

## Parallelism map

```
Phase 0  ──► Phase 1 (builder: ocha/app/)  ──►  Phase 2  ──►  Phase 3
```

Phase 1 is the only code-editing phase. Phase 2 waits for Phase 1.
Phase 3 is the final sync.

No parallel file overlap — builder owns `ocha/app/`, reviewer owns
`ocha/tests/`, coordinator owns `docs/`, lead owns `planning/`.

---

## File ownership (conflict-free zones)

| Role | Owned path | Files touched |
|------|-----------|---------------|
| Coordinator | `ocha/docs/` | Execution brief (already written) |
| Lead | `planning/` | This plan |
| Builder | `ocha/app/` | `widgets.py`, `app.py` |
| Reviewer | `ocha/tests/` | `test_app.py` (add regression tests) |

---

## Success criteria

- [ ] Sidebar does not flicker/rebuild when only elapsed time changes
- [ ] Output pane does not yank scroll position when content is unchanged
- [ ] Output pane auto-scrolls only when user is already at bottom
- [ ] `refresh_from_state()` short-circuits when nothing changed
- [ ] Event-driven refresh fires on real state mutations
- [ ] Slow poll (5 s) handles only cosmetic elapsed-time updates
- [ ] `pytest ocha/tests/` passes (existing + new regression tests)
- [ ] Changes committed and pushed on `agent` branch
