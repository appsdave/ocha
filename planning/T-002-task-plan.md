# T-002 Task Plan — OutputPane scrollbar glitch fix

> Lead: planner · Branch: `agent`  
> Created: 2026-03-19 22:13  
> Source: `docs/T-002-execution-brief.md`

---

## Ordered Steps

### Step 1 — Add fingerprint cache to `_tick` in `app.py`

**Builder** · File: `ocha/app/app.py`

Add a `_last_tick_fingerprint` attribute to `OchaApp.__init__`.  
In `_tick`, compute a lightweight fingerprint from the selected task's
`(task_id, status, output mode, workflow_log length, raw_log length)` and
the set of `(task_id, status)` for all tasks.  
Skip `refresh_from_state()` when the fingerprint matches the cached value.

**Verification:**
- `_tick` no longer calls `refresh_from_state()` when output hasn't changed.
- `_tick` still triggers refresh when a new log line arrives or status changes.
- No other callers of `refresh_from_state()` are affected.

---

### Step 2 — Add fast fingerprint early-return to `OutputPane.update_task`

**Builder** · File: `ocha/app/widgets.py` (lines 141-179)

Store `_last_fingerprint = (task_id, mode, line_count)` on `OutputPane`.  
At the top of `update_task`, compute the fingerprint from the incoming
`task`/`mode` and early-return if it matches — **before** iterating lines
or building the markup string.  
Keep the existing `_last_content` string guard as a secondary safety net.

**Verification:**
- When called with identical task output, method returns before line 154.
- When a new line is appended, fingerprint changes and markup is rebuilt.
- The `task is None` path is still handled correctly (no fingerprint match).

---

### Step 3 — Defer `scroll_end` to post-layout via `call_after_refresh`

**Builder** · File: `ocha/app/widgets.py` (line 179)

Replace:
```python
self.scroll_end(animate=False)
```
with:
```python
self.call_after_refresh(self.scroll_end, animate=False)
```

This ensures the scroll target uses the content height **after** Textual
commits the new Static widget layout.

**Verification:**
- After content update, scroll lands at the true bottom (no intermediate jump).
- User does not see a flash of wrong scroll position on rapid updates.

---

### Step 4 — Widen `_is_at_bottom` tolerance

**Builder** · File: `ocha/app/widgets.py` (lines 135-139)

Change:
```python
return self.scroll_y >= self.max_scroll_y - 2
```
to:
```python
return self.scroll_y >= self.max_scroll_y - max(3, self.size.height // 4)
```

**Verification:**
- Scrolling up a few lines no longer breaks auto-scroll-to-bottom.
- Scrolling up significantly (past 25 % of viewport) disables auto-scroll.

---

### Step 5 — Add `_last_content` cache to `TaskHeader.update_task`

**Builder** · File: `ocha/app/widgets.py` (lines 96-125)

Add `_last_content: str = ""` class attribute to `TaskHeader`.  
In `update_task`, build the markup string into a local variable, compare
against `_last_content`, and early-return if identical.

**Verification:**
- Repeated calls with the same task data do not trigger `self.update()`.
- Changing task status or elapsed time still triggers the update.

---

### Step 6 — Add scroll-stability tests

**Builder / Reviewer** · File: `ocha/tests/test_app.py` (new tests)

Using the Textual `pilot` test harness:

1. Mount `OchaApp` with a task that produces growing output.
2. Assert `OutputPane.scroll_y` follows bottom when user hasn't scrolled up.
3. Scroll the OutputPane up, inject more output, and assert `scroll_y`
   stays at the user's position (does not snap to bottom).
4. Verify `TaskHeader` doesn't call `update()` when content is unchanged
   (can spy/mock `Static.update`).

**Verification:**
- Both test cases pass.
- All existing tests in `ocha/tests/` still pass (`pytest ocha/tests/`).

---

## File Ownership

| Step | File | Owner |
|------|------|-------|
| 1 | `ocha/app/app.py` | builder |
| 2 | `ocha/app/widgets.py` | builder |
| 3 | `ocha/app/widgets.py` | builder |
| 4 | `ocha/app/widgets.py` | builder |
| 5 | `ocha/app/widgets.py` | builder |
| 6 | `ocha/tests/test_app.py` | builder / reviewer |

Steps 2–5 all touch `widgets.py` — they **must be done sequentially by
one builder** to avoid merge conflicts. Step 1 (`app.py`) is independent
and can be done in parallel with steps 2–5 if needed, but sequential is
safest on a shared branch.

---

## Risk Notes

1. **Same-file overlap (widgets.py):** Steps 2–5 all edit `widgets.py`.
   One builder should own all four and commit them atomically or in a
   single sequential pass. Do **not** split across workers.

2. **`call_after_refresh` availability:** Verify the Textual version in
   use exposes `Widget.call_after_refresh`. If not available, fall back to
   `self.set_timer(0, lambda: self.scroll_end(animate=False))`.

3. **Fingerprint collisions (Step 2):** Using `len(lines)` as a proxy
   assumes lines are append-only. If a line can be *replaced* (same count,
   different content), the `_last_content` string guard still catches it.
   Keep both guards.

4. **Test flakiness (Step 6):** Textual pilot tests that depend on scroll
   position may need `await pilot.pause()` after content injection to
   allow layout to settle.

---

## Execution Order Summary

```
Builder:  Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6
Reviewer: Review after Step 5 (code), then after Step 6 (tests)
```

All work on branch `agent`. Atomic commits per step recommended.
