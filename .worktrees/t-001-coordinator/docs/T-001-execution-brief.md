# T-001 Execution Brief

> **Coordinator:** S-001-01 · **Branch:** `agent`

---

## Goal (refined)

The operator wants to remove the grey visual indicator that appears on the selected/highlighted task row in the TUI's sidebar `ListView` when a shell process (Junie worker) is active. In Textual 0.89.1, the `ListView` applies a grey "blurred cursor" background (`$block-cursor-blurred-background`) to the highlighted `ListItem` when the list does not have focus, and a `background-tint: $foreground 5%` when it does. The app's inline CSS in `app.py` attempts to override this with `ListView > ListItem.--highlight { background: #282828; }` (lines 115-121), but Textual 0.89.1 uses the single-dash class `.-highlight` in its default CSS, so the override never matches and the grey bleeds through. The fix must ensure the grey highlight/tint is fully suppressed so the selected row blends with the dark background (`#282828`) at all times, keeping only the green `border-left` as the selection indicator.

---

## Relevant files

| File | Role | Purpose |
|------|------|---------|
| `ocha/app/app.py` | **edit** | Contains inline CSS (lines 23-199) with `ListView > ListItem.--highlight` rules that need the class name fixed |
| `ocha/app/widgets.py` | read | `WorkerListItem`, `AgentsPane` — compose the ListView; green border-left is the only desired selection indicator |
| `ocha/app/state.py` | read | `AppState`, `WorkerStatus` — understand active/running states (no changes needed) |

---

## Recommended changes

### Phase 1 — Fix the CSS overrides in `app.py` (builder)

1. **Update the `ListItem` highlight selectors** (lines 115-122 of `app.py`). Change `.--highlight` to `.-highlight` to match Textual 0.89.1's actual class name. The rules should be:

   ```css
   ListView > ListItem.-highlight {
       background: #282828;
       color: #ebdbb2;
       text-style: none;
   }

   ListView:focus > ListItem.-highlight {
       background: #282828;
       color: #ebdbb2;
       text-style: none;
       border-left: thick #b8bb26;
   }
   ```

2. **Remove the `background-tint` on focused ListView.** Add an explicit rule to suppress Textual's default 5% foreground tint:

   ```css
   ListView:focus {
       background-tint: transparent;
   }
   ```

3. **Suppress the hover background** if it also shows grey. Add:

   ```css
   ListView > ListItem.-hovered {
       background: #282828;
   }
   ```

### Phase 2 — Verify (reviewer)

4. Launch the TUI and create a task to spawn a running shell. Confirm:
   - No grey background appears on the highlighted row when the list is focused.
   - No grey background appears on the highlighted row when focus moves away (e.g., to the output pane).
   - The green `border-left: thick #b8bb26` still appears on the selected row when the list is focused.
   - Hover does not introduce a grey background.

---

## Safe partitioning

| Directory / File | Owned by | Notes |
|------------------|----------|-------|
| `docs/` | coordinator | Execution brief lives here |
| `ocha/app/app.py` (CSS block, lines 23-199) | builder | Only the inline CSS string needs editing — no logic changes |
| `ocha/app/widgets.py` | builder (read-only) | Reference only; no edits expected |
| `ocha/app/state.py` | — | No changes needed |
| `ocha/tests/` | reviewer | Run existing tests to check for regressions |

---

## Key details for downstream

- **Textual version:** 0.89.1 (installed in `ocha/.venv/`)
- **CSS location:** Inline Python string `CSS = """..."""` in `ocha/app/app.py`, lines 23-199.
- **Root cause:** Textual's default `ListView` CSS applies `$block-cursor-blurred-background` (a grey color) to `ListItem.-highlight`. The app tried to override this but used `.--highlight` (double-dash) instead of `.-highlight` (single-dash), so the override never takes effect.
- **Branch:** All work stays on `agent`. No new branches.
