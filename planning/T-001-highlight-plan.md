# T-001 Task Plan — Better Highlighting of Current Focus Area

**Lead:** S-001-02
**Branch:** agent
**Date:** 2026-03-19

---

## Overview

The operator cannot tell which TUI pane is active because all pane borders
use the same dim color (`#504945`).  The fix is purely CSS: add
`:focus-within` rules so the focused pane's border brightens to `#b8bb26`
(Gruvbox accent green).  This is a single-file edit in `ocha/app/app.py`
(CSS string constant only, no Python logic).

All work stays on the shared `agent` branch.

---

## Task breakdown

### Step 1 — Add `:focus-within` border rules for main panes

**Worker:** builder
**Owned files:** `ocha/app/app.py` (CSS block, lines 34–60)
**Depends on:** nothing

Insert three `:focus-within` rules immediately after each pane's base rule
in the CSS string constant:

```css
#agents-pane:focus-within {
    border: solid #b8bb26;
}
#task-header:focus-within {
    border: solid #b8bb26;
}
#output-pane:focus-within {
    border: solid #b8bb26;
}
```

Rules:
- Place each `:focus-within` block directly after its corresponding base
  rule (e.g., `#agents-pane:focus-within` right after `#agents-pane`).
- Do NOT modify existing rules — only add new ones.
- Keep the existing `ListView > ListItem.--highlight` and
  `ListView:focus > ListItem.--highlight` rules unchanged.

---

### Step 2 — Review and validate

**Worker:** reviewer
**Owned files:** read-only on `ocha/app/app.py`, `ocha/app/widgets.py`
**Depends on:** Step 1

---

## File ownership

| File | Step | Role | Edit type |
|------|------|------|-----------|
| `ocha/app/app.py` (CSS block) | 1 | builder | add 3 CSS rule blocks |
| `ocha/app/app.py` | 2 | reviewer | read-only review |
| `ocha/app/widgets.py` | 2 | reviewer | read-only review |

---

## Verification criteria

| # | Check | How |
|---|-------|-----|
| 1 | Three new `:focus-within` rules exist for `#agents-pane`, `#task-header`, `#output-pane` | Grep for `:focus-within` in the CSS block |
| 2 | Each rule sets `border: solid #b8bb26` | Inspect the CSS string |
| 3 | No existing rules were modified or removed | Diff against `agent` baseline |
| 4 | CSS string is valid (no unclosed braces, no syntax errors) | App starts without CSS parse errors |
| 5 | Existing tests pass | `python -m pytest tests/ -v` |
| 6 | Visual: focused pane border turns green, unfocused panes stay dim | Manual run with `python -m ocha`, press Tab/h/l |

---

## Risk notes

- **Textual version:** `:focus-within` requires Textual ≥ 0.40. If an
  older version is installed, the builder should fall back to toggling a
  CSS class via `on_focus`/`on_blur` widget events.  Check with
  `pip show textual` before editing.
- **`#task-header` caveat:** This pane contains a `Static` widget which
  is not focusable by default. The `:focus-within` rule is harmless but
  will only activate if a focusable child is added later.
- **No file overlap:** Only one file is edited in one step, so there is
  zero merge risk.

---

## Execution order

```
┌──────────────┐
│   Step 1     │  builder — add CSS rules to app.py
│   app.py     │
└──────┬───────┘
       │
┌──────▼───────┐
│   Step 2     │  reviewer — validate changes + run tests
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

> Produced execution plan with 2 steps: one builder session adds 3 CSS
> `:focus-within` rules to `ocha/app/app.py`, then one reviewer session
> validates.  Single-file edit, zero merge risk, all on `agent` branch.
