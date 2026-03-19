# T-001 — Better Highlighting of Current Focus Area

## Execution Brief

### 1. Goal (refined)

The operator finds it hard to tell which TUI pane (agents sidebar, task header, output log) is currently active because every pane border is the same dim color (`#504945`).  The task is to make the **active/focused pane's border visually pop** — specifically by brightening the side-line (border) of whichever container currently holds keyboard focus.  The `ListView` item highlight already changes color on focus (green `#b8bb26` vs gray `#928374`), but the surrounding pane borders do not.  The fix should add `:focus-within` CSS rules for the three main panes so their borders brighten to the Gruvbox accent green when any child widget inside them has focus.

### 2. Relevant files

| File | Role | Why |
|---|---|---|
| `ocha/app/app.py` (lines 22-188, CSS block) | **edit** | All pane border colors live here. Add `:focus-within` rules for `#agents-pane`, `#task-header`, `#output-pane`. |
| `ocha/app/app.py` (lines 98-111, ListView highlight) | **read** | Already has focus-aware highlight — verify it still looks right after pane-border changes. |
| `ocha/app/widgets.py` | **read** | Widget IDs and composition — confirms which containers map to which pane IDs. |
| `ocha/tests/test_app.py` | **edit** | Add or extend a snapshot/unit test that verifies the focused pane gets the bright border class. |

### 3. Recommended changes

**Phase 1 — CSS changes (builder, `ocha/app/app.py`)**

1. Add `:focus-within` rules for the three main pane IDs that brighten the border from `#504945` → `#b8bb26` (Gruvbox green):

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

2. Optionally, also brighten the pane title color inside the focused pane so the label and border match:

   ```css
   #agents-pane:focus-within .pane-title {
       color: #fabd2f;
   }
   ```

3. Keep the existing `ListView > ListItem.--highlight` and `ListView:focus > ListItem.--highlight` rules unchanged — they already work correctly and complement the new pane-level highlight.

**Phase 2 — Validation (reviewer)**

4. Run the app (`python -m ocha` or the installed entry point) and visually verify:
   - Pressing `h`/`l`/`tab` changes which pane has the bright green border.
   - Only one pane border is bright at a time.
   - The unfocused panes revert to `#504945`.

5. Run existing tests to ensure no regressions:
   ```bash
   cd ocha && python -m pytest tests/ -v
   ```

### 4. Safe partitioning

| Owned directory | Role | Notes |
|---|---|---|
| `docs/` | coordinator | This brief and any follow-up docs. |
| `ocha/app/app.py` (CSS block only) | builder | Only the CSS string constant; no Python logic changes needed. |
| `ocha/tests/` | reviewer | Validation and optional new test. |

All work stays on the shared `agent` branch. No new branches needed.

### 5. Risk notes

- Textual's `:focus-within` pseudo-class is supported since Textual ≥ 0.40. Verify the installed version (`pip show textual`) supports it; if not, an alternative is to use `on_focus`/`on_blur` widget events to toggle a CSS class manually.
- The `#task-header` is a plain `Static` and never directly receives focus, so its `:focus-within` rule will only fire if a focusable child is added later. This is harmless but worth noting.
