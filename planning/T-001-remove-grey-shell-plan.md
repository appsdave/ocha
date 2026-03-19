# T-001 Task Plan — Remove Grey Active Shell from Task List

**Lead:** S-001-02
**Branch:** agent
**Date:** 2026-03-19

---

## Overview

The operator wants the grey left-border "active shell" removed from
unfocused highlighted task list items.  When a `ListView` item is
highlighted but not focused, the CSS rule `ListView > ListItem.--highlight`
currently draws a `border-left: thick #928374` (grey side-line).  Since the
focused state already shows a bright green border (`#b8bb26`), the grey
border is redundant.

The fix is a one-line CSS removal in `ocha/app/app.py`.  The coordinator
has already applied the change and confirmed all 43 tests pass.

All work stays on the shared `agent` branch.

---

## Task breakdown

### Step 1 — Remove grey border-left from unfocused highlight rule

**Worker:** builder
**Owned files:** `ocha/app/app.py` (CSS block, line ~117)
**Depends on:** nothing

Remove the `border-left: thick #928374;` line from the
`ListView > ListItem.--highlight` rule in the CSS string constant.

**Before:**
```css
ListView > ListItem.--highlight {
    background: #282828;
    border-left: thick #928374;
}
```

**After:**
```css
ListView > ListItem.--highlight {
    background: #282828;
}
```

Rules:
- Do NOT modify the focused highlight rule (`ListView:focus > ListItem.--highlight`) — its bright green border must remain.
- Do NOT change the `background` value.
- Only remove the single `border-left` property line.

---

### Step 2 — Review and validate

**Worker:** reviewer
**Owned files:** read-only on `ocha/app/app.py`, `ocha/app/widgets.py`
**Depends on:** Step 1

---

## File ownership

| File | Step | Role | Edit type |
|------|------|------|-----------|
| `ocha/app/app.py` (CSS block) | 1 | builder | remove 1 CSS property line |
| `ocha/app/app.py` | 2 | reviewer | read-only review |
| `ocha/app/widgets.py` | 2 | reviewer | read-only reference |

---

## Verification criteria

| # | Check | How |
|---|-------|-----|
| 1 | `border-left` is absent from the unfocused highlight rule | Grep: no `#928374` in the CSS block |
| 2 | Focused highlight rule still contains `border-left: thick #b8bb26` | Grep for `#b8bb26` in the CSS block |
| 3 | `background: #282828` preserved in both highlight rules | Inspect the CSS string |
| 4 | CSS string is valid (no unclosed braces, no syntax errors) | App starts without CSS parse errors |
| 5 | Existing tests pass | `.venv/bin/python -m pytest tests/ -v` — 43 passed |
| 6 | Visual: unfocused highlight has no side-line; focused highlight shows green | Manual run with `.venv/bin/python -m ocha` |

---

## Risk notes

- **Zero merge risk:** Single property removal in one file, no overlap
  with any other active task's file ownership.
- **No logic change:** Pure CSS edit, no Python code affected.
- **Coordinator pre-applied:** The coordinator session already made this
  change and confirmed tests pass.  Builder step is effectively a
  confirmation/no-op if the change is already on branch.

---

## Execution order

```
┌──────────────┐
│   Step 1     │  builder — remove border-left from app.py CSS
│   app.py     │
└──────┬───────┘
       │
┌──────▼───────┐
│   Step 2     │  reviewer — validate change + run tests
│   read-only  │
└──────────────┘
```

**Session grouping:**

| Session | Step | Role |
|---------|------|------|
| Builder | 1 | builder |
| Reviewer | 2 | reviewer |

Sequential only — reviewer runs after builder completes.

---

## Lead summary (for TUI event)

> Produced task plan with 2 steps: builder removes the grey `border-left`
> from the unfocused highlight CSS rule in `ocha/app/app.py`, then reviewer
> validates.  Single-line removal, zero merge risk, all on `agent` branch.
> Coordinator has already applied the fix and all 43 tests pass.
