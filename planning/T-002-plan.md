# T-002 Execution Plan

> Lead: planning/T-002-plan.md
> Date: 2026-03-19
> Branch: `agent`
> Source: docs/T-002-execution-brief.md (coordinator output)

---

## Phase 0 — Branch bootstrap (coordinator)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 0.1 | Create `agent` branch from current `main` HEAD | coordinator | `git branch agent main && git checkout agent` in the main repo. Verify with `git rev-parse --verify agent`. |
| 0.2 | Verify worktrees can attach to `agent` | coordinator | Confirm `.worktrees/` entries are compatible. |

**Gate:** `git rev-parse --verify agent` succeeds before any builder work starts.

---

## Phase 1 — Builder: UI glitch fixes + branch constant (parallel-safe)

All edits scoped to `ocha/app/`. No other role touches these files.

| # | Action | File(s) | Details |
|---|--------|---------|---------|
| 1.1 | Fix sidebar flicker — diff-based rebuild | `ocha/app/widgets.py` | In `AgentsPane.load()`: instead of `clear()` + full rebuild every tick, compare current task IDs + statuses to previous state. Only update changed `ListItem` widgets in place. Add a `_prev_snapshot` attribute to track last-rendered state. |
| 1.2 | Fix output pane auto-scroll | `ocha/app/widgets.py` or `ocha/app/app.py` | In `OutputPane.update_task()`: track last-seen line count. Only call `scroll_end()` when new lines were appended. |
| 1.3 | Improve highlight visibility (optional) | `ocha/app/app.py` (CSS block) | Change `ListView > ListItem.--highlight` background from `#282828` to `#3c3836`. |
| 1.4 | Fix branch constant mismatch | `ocha/app/app.py` line 19 | Change `OCHA_BRANCH = "ocha"` → `OCHA_BRANCH = "agent"`. |
| 1.5 | Fix `_post_pipeline_git_flow` | `ocha/app/app.py` lines 594–663 | Stop creating `ocha/<task-id>` branches. Commit and push on `agent` directly. Remove checkout-back-to-main logic. Keep optional PR creation targeting `main` from `agent`. |

**Gate:** `pytest ocha/tests/` passes with all Phase 1 changes applied.

---

## Phase 2 — Lead: Markdown documentation updates (parallel-safe)

All edits scoped to markdown files outside `ocha/app/`. No overlap with builder.

| # | Action | File | Details |
|---|--------|------|---------|
| 2.1 | Update README branch references | `ocha/README.md` | Replace any `ocha` branch references with `agent`. Document `agent` as the shared working branch. |
| 2.2 | Check python-textual-rebuild.md | `ocha/python-textual-rebuild.md` | Update any branch references from `ocha` → `agent`. |
| 2.3 | Check junie-headless-sessions.md | `ocha/junie-headless-sessions.md` | Update any branch references from `ocha` → `agent`. |
| 2.4 | Verify role docs already correct | `ocha/app/roles/*.md` | Confirm coordinator.md, lead.md, builder.md, reviewer.md already say `agent`. No edits expected. |

**Gate:** No stale `ocha` branch references remain in any `.md` file (grep clean).

---

## Phase 3 — Reviewer: Validation

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 3.1 | Run full test suite | reviewer | `pytest ocha/tests/ -v` — all tests must pass. |
| 3.2 | Verify branch constant alignment | reviewer | `OCHA_BRANCH` in app.py == `SHARED_BRANCH` in orchestrator.py == `"agent"`. |
| 3.3 | Verify no sidebar flicker | reviewer | Read `AgentsPane.load()` and confirm diff-based update logic is present. |
| 3.4 | Verify scroll behavior | reviewer | Confirm `scroll_end()` is gated on new content. |
| 3.5 | Grep for stale branch refs | reviewer | `grep -rn '"ocha"' ocha/app/` should return zero hits for branch-name strings. `grep -rn 'ocha/' ocha/app/app.py` should not find per-task branch creation. |

---

## Phase 4 — Sync: Commit & push

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 4.1 | Stage all changes | coordinator | `git add -A` on `agent` branch. |
| 4.2 | Commit | coordinator | `git commit -m "T-002: fix UI glitching, align branch model to agent, update docs"` |
| 4.3 | Push | coordinator | `git push -u origin agent` |

---

## Parallelism map

```
Phase 0  ──► Phase 1 (builder: ocha/app/)  ──►  Phase 3  ──►  Phase 4
              Phase 2 (lead: markdown docs)  ──►
```

Phases 1 and 2 run in parallel — zero file overlap.
Phase 3 waits for both.
Phase 4 is the final sync.

---

## Success criteria

- [ ] `agent` branch exists and is checked out
- [ ] TUI sidebar does not flicker on 2-second refresh when task list is unchanged
- [ ] Output pane does not auto-scroll when no new content arrived
- [ ] `OCHA_BRANCH` == `SHARED_BRANCH` == `"agent"`
- [ ] `_post_pipeline_git_flow` stays on `agent`, no per-task branches
- [ ] All markdown files reference `agent` as the shared branch
- [ ] `pytest ocha/tests/` passes
- [ ] Changes pushed to `origin/agent`
