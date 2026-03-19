# T-002 Execution Brief — Workflow-area scrollbar glitch

> Coordinator output for task T-002.  
> Updated: 2026-03-19 22:10  
> Branch: `agent`

## Operator request (paraphrased)

The scrollbar inside the workflow area (OutputPane) is glitchy and causes
everything that opens there to glitch. Fix the scrollbar instability.

---

## Status of prior brief items

Several issues from the original T-002 brief have **already been fixed** in the
current codebase:

- ✅ `OCHA_BRANCH` is now `"agent"` (app.py line 19) — branch mismatch resolved.
- ✅ `_post_pipeline_git_flow` now stays on the shared `agent` branch — no per-task branches.
- ✅ `AgentsPane.load` now uses in-place label updates instead of full DOM rebuild (widgets.py lines 65-93).

The **remaining issue** is the OutputPane scrollbar glitch described below.

---

## 1 — OutputPane scrollbar glitch: root causes

### 1a. `_tick` triggers `refresh_from_state()` every 2s even when nothing changed

**File:** `ocha/app/app.py` lines 296-303

The `_tick` method fires every 2 seconds. If *any* task is RUNNING or QUEUED, it
calls `refresh_from_state()` which rebuilds all three panels (AgentsPane,
TaskHeader, OutputPane). For the OutputPane this means reconstructing the full
Rich markup string and calling `Static.update()` — which triggers a Textual
layout reflow inside the `VerticalScroll` container, resetting scroll extents
and causing the scrollbar to jump.

**Fix:** Cache a lightweight fingerprint of the selected task's output (e.g.
`(task_id, mode, len(workflow_log), len(raw_log))` per worker) and skip
`refresh_from_state()` entirely when unchanged.

### 1b. `OutputPane.update_task` rebuilds markup on every call

**File:** `ocha/app/widgets.py` lines 141-179

Even though there is a `_last_content` string comparison guard (line 170-171),
the method still:
1. Queries the DOM for `#output-content`
2. Iterates all output lines and builds the full Rich markup string
3. Only *then* compares against `_last_content`

This is wasteful, and the string comparison itself is O(n) on potentially large
log output. A cheaper fingerprint check should come first.

**Fix:** Store `(task_id, mode, total_line_count)` as a fast fingerprint.
Early-return before building markup when the fingerprint matches.

### 1c. `scroll_end` fires before Textual commits new layout

**File:** `ocha/app/widgets.py` line 179

After `content.update(new_text)`, the code calls `self.scroll_end(animate=False)`
synchronously. But Textual hasn't yet committed the new content height from the
updated Static widget — so `scroll_end` scrolls to the *old* `max_scroll_y`.
On the next layout pass, content grows taller, leaving the viewport in an
intermediate position. This is the most visible cause of the "everything
glitches" behavior.

**Fix:** Replace `self.scroll_end(animate=False)` with
`self.call_after_refresh(self.scroll_end, animate=False)` so the scroll target
uses the post-layout content height.

### 1d. `_is_at_bottom` tolerance too tight

**File:** `ocha/app/widgets.py` lines 135-139

The heuristic uses `self.scroll_y >= self.max_scroll_y - 2`, but when content
grows by 1-2 lines per update, partial-line rendering can put `scroll_y` just
outside this window, causing auto-scroll to trigger (or not) unpredictably.

**Fix:** Widen tolerance to `max(3, self.size.height // 4)`.

### 1e. `TaskHeader.update_task` has no content-diff guard

**File:** `ocha/app/widgets.py` lines 97-125

Unlike OutputPane, TaskHeader calls `self.update()` on every tick with no
caching. This causes unnecessary layout churn in the same frame.

**Fix:** Add a `_last_content` cache identical to the OutputPane pattern.

---

## 2 — Relevant files

| File | Role | Read / Edit |
|------|------|-------------|
| `ocha/app/widgets.py` | OutputPane, TaskHeader | **Edit** — primary fix target |
| `ocha/app/app.py` | `_tick`, `refresh_from_state`, CSS | **Edit** — reduce tick churn |
| `ocha/app/state.py` | `OchaTask.output_lines`, `AppState` | Read (reference) |
| `ocha/tests/test_app.py` | Existing app tests | **Edit** — add scroll-stability test |

---

## 3 — Recommended changes

### Phase 1 — Fix the scrollbar glitch (builder · `ocha/app/`)

1. **`app.py` `_tick`**: Add a fingerprint cache; skip `refresh_from_state()`
   when the selected task's output lengths and statuses haven't changed.

2. **`widgets.py` `OutputPane.update_task`**: Add a fast `(task_id, mode,
   line_count)` fingerprint check before building markup. Early-return when
   unchanged.

3. **`widgets.py` `OutputPane.update_task`**: Replace
   `self.scroll_end(animate=False)` with
   `self.call_after_refresh(self.scroll_end, animate=False)`.

4. **`widgets.py` `OutputPane._is_at_bottom`**: Widen tolerance from `2` to
   `max(3, self.size.height // 4)`.

5. **`widgets.py` `TaskHeader.update_task`**: Add `_last_content` caching to
   skip identical updates.

### Phase 2 — Tests (builder or reviewer · `ocha/tests/`)

6. Add a Textual `pilot` test that mounts `OchaApp` with a task producing
   growing output and asserts:
   - `OutputPane.scroll_y` stays stable when user has scrolled up.
   - `OutputPane.scroll_y` follows bottom when user hasn't scrolled.

7. Ensure all existing tests pass (`pytest ocha/tests/`).

---

## 4 — Safe partitioning

| Owned directory | Role | Scope |
|-----------------|------|-------|
| `docs/` | coordinator | This brief; no code edits |
| `ocha/app/` | builder | All widget and app-level fixes (Phase 1) |
| `ocha/tests/` | builder / reviewer | Scroll-stability tests (Phase 2) |
| `planning/` | lead | Task plan updates if needed |

All work stays on the shared **`agent`** branch. Builder should make atomic
commits per phase so the reviewer can inspect each change in isolation.

---

## 5 — Success criteria

- [ ] OutputPane does not auto-scroll when no new content arrived
- [ ] OutputPane scrollbar stays stable when user has scrolled up mid-log
- [ ] `scroll_end` fires after layout commit (no intermediate scroll position)
- [ ] TaskHeader skips update when content is identical
- [ ] `_tick` skips full refresh when selected task output is unchanged
- [ ] Existing tests pass (`pytest ocha/tests/`)

---

## 6 — TUI event summary

```
[coordinator] T-002 brief updated — 5 scroll-glitch root causes in OutputPane identified (layout reflow on tick, premature scroll_end, tight _is_at_bottom tolerance, missing TaskHeader cache). Builder: widgets.py + app.py. Phase 1 = fix scroll, Phase 2 = add tests.
```
