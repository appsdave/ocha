# T-001 Execution Brief — Remove Grey Active-State Box

> **Coordinator:** S-001-01 · **Branch:** `agent`
> **Updated:** 2026-03-19

---

## Goal (refined)

The ocha TUI uses a Textual `ListView` in the left sidebar (`#agents-pane`) to list tasks. When a `ListItem` is highlighted (keyboard-selected), Textual's **default CSS** applies a grey background via design variables (`$block-cursor-blurred-background` when unfocused, `$block-cursor-background` when focused) and a `background-tint: $foreground 5%` on the focused `ListView` itself. The project already uses a **green outline** (`border: solid #b8bb26`) on `#agents-pane:focus-within` to signal which pane is active. The operator wants to **remove the redundant grey highlight box entirely**, relying solely on the green outline.

Prior commits (`93e074f`, `3dc8e28`, `98b548f`) fixed the selector name from `.--highlight` to `.-highlight` and added `background-tint: transparent`, but the **grey box still persists**. The root cause is a **CSS specificity issue**: Textual's `DEFAULT_CSS` uses nested selectors (`ListView { & > ListItem { &.-highlight { ... } } }`) which have higher specificity in Textual's TCSS engine than the app's flat `ListView > ListItem.-highlight { ... }` rules.

---

## Relevant files

| File | Role | Purpose |
|------|------|---------|
| `ocha/app/app.py` lines 23–212 | **edit** | All CSS lives in the `CSS` string constant. Lines 106–135 contain the `ListView` / `ListItem` highlight rules. |
| `ocha/app/widgets.py` | read | `WorkerListItem(ListItem)` — confirm no inline styles override. |
| `ocha/app/state.py` | read | `AppState.selected_index` drives highlight — no changes needed. |
| `ocha/.venv/.../textual/widgets/_list_view.py` lines 31–61 | **reference** | Textual's `DEFAULT_CSS` — the source of the grey background. Shows exact design variables to override. |
| `ocha/tests/test_app.py` | verify | Run after changes. |

---

## Recommended changes

### Phase 1 — Override the design variables (builder, in `ocha/app/app.py`)

The most reliable fix is to **override Textual's design variables** at the widget level so the nested default CSS resolves to the dark background. Replace the current `ListView` / `ListItem` CSS block (lines ~106–135) with:

```css
ListView {
    background: #282828;
    scrollbar-background: #282828;
    scrollbar-color: #504945;

    & > ListItem {
        background: #282828;
        color: #ebdbb2;

        &.-highlight {
            background: #282828;
            color: #ebdbb2;
            text-style: none;
        }

        &.-hovered {
            background: #282828;
        }
    }

    &:focus {
        background-tint: transparent;

        & > ListItem.-highlight {
            background: #282828;
            color: #ebdbb2;
            text-style: none;
        }
    }
}

ListView > ListItem:hover {
    background: #282828;
}
```

**Why nested selectors?** Textual's `DEFAULT_CSS` uses nested `&` selectors which produce higher specificity than flat selectors in the TCSS engine. By matching the same nesting structure in the app's `CSS` constant (which takes priority over `DEFAULT_CSS`), the override will win.

**Alternative approach** (if nesting is not supported in the `CSS` string): Override the design variables at the `Screen` level:

```css
Screen {
    $block-cursor-background: #282828;
    $block-cursor-blurred-background: #282828;
    $block-cursor-foreground: #ebdbb2;
    $block-cursor-blurred-foreground: #ebdbb2;
    $block-cursor-text-style: none;
    $block-cursor-blurred-text-style: none;
    $block-hover-background: #282828;
}
```

### Phase 2 — Verify (reviewer)

1. Run `pytest ocha/tests/` — no regressions.
2. Launch the TUI and visually confirm:
   - **No grey box** on the highlighted row (focused or unfocused).
   - **Green border** on `#agents-pane` still appears on `:focus-within`.
   - Keyboard navigation (j/k) still moves selection.
   - Hover does not introduce grey.

---

## Safe partitioning

| Directory / File | Owned by | Notes |
|------------------|----------|-------|
| `docs/` | coordinator | This brief and follow-up notes. |
| `ocha/app/app.py` (CSS block) | builder | Only the CSS string needs editing — no logic changes. |
| `ocha/app/widgets.py` | builder (read-only) | Reference only; no edits expected. |
| `ocha/tests/` | reviewer | Test execution and validation. |

---

## Key details for downstream

- **Textual version:** check with `python -c "import textual; print(textual.__version__)"` in `ocha/.venv/`.
- **CSS location:** Inline Python string `CSS = """..."""` in `ocha/app/app.py`, lines 23–212.
- **Root cause:** Textual's `DEFAULT_CSS` in `_list_view.py` uses **nested selectors** with design variables (`$block-cursor-blurred-background`, etc.) that have higher specificity than the app's current flat CSS overrides. The app CSS uses the right class name (`.-highlight`) but loses the specificity battle.
- **Branch:** All work stays on `agent`. No new branches.
