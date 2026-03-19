# How Junie works in `ocha` headless sessions

This note explains the operating concept behind how `ocha` uses Junie, especially when it spawns additional agents or sessions without opening an interactive IDE window.

It is a conceptual document, not a strict implementation spec.

## The short version

In `ocha`, Junie should be thought of as a **headless coding worker** that can be launched repeatedly by the orchestrator.

That means:

- one operator starts a top-level task from the TUI
- `ocha` turns that task into a sequence of Junie-driven sessions
- some sessions act like planners or coordinators
- some sessions act like builders or reviewers
- each spawned session runs against an isolated worktree
- all of them still follow the shared branch model centered on `agent`

So `ocha` is not using Junie as a single chat tab. It is using Junie as a reusable execution unit inside a larger orchestration loop.

## The core idea: one parent workflow, many Junie sessions

The operator interacts with one `ocha` session, but under the hood the system may create multiple Junie runs.

Typical flow:

1. the operator submits one high-level task
2. `ocha` launches a Junie session to expand or clarify that task
3. `ocha` launches another Junie session to plan sub-work
4. `ocha` launches one or more builder Junie sessions in isolated worktrees
5. `ocha` optionally launches reviewer Junie sessions against those same worktrees
6. `ocha` synchronizes results back onto the shared branch line

The important point is that the extra agents are really **new Junie sessions with different roles**, not separate magical subsystems.

## What “headless” means here

Headless means the Junie session is started programmatically instead of being driven manually through a visible IDE conversation.

In practical terms, a headless Junie session should be treated like a subprocess or worker job that:

- receives a prepared prompt
- receives execution constraints
- runs in a known repository/worktree path
- streams logs/events back to `ocha`
- exits with a result, failure, or retry signal

The operator should still be able to observe the outcome through the `ocha` TUI, but the operator does not need to manually open each Junie worker and steer it by hand.

## How `ocha` should think about Junie roles

The easiest way to reason about the system is to treat Junie as role-driven.

### 1. Coordinator Junie session

Purpose:

- refine the original request
- gather project-facing context
- produce a stronger prompt for downstream work

This session should usually work from the main operator context and does not need to create lots of code changes itself.

### 2. Lead Junie session

Purpose:

- break the task into subtasks
- decide whether the work can be parallelized safely
- assign subtasks to separate repo areas when possible

This is the role that protects the shared-branch model from chaos. If the lead assigns two sessions to the same files unnecessarily, the system will create its own merge pain.

### 3. Builder Junie session

Purpose:

- make the actual code/doc/test edits
- run the needed verification for its subtask
- prepare the worktree result for sync

Each builder should run in its own isolated worktree even if all builders eventually push to `agent`.

### 4. Reviewer Junie session

Purpose:

- inspect what the builder changed
- catch obvious mistakes or missing checks
- confirm whether the work is ready to sync

This can run in the same worktree after the builder completes so it reviews the exact filesystem state the builder produced.

## Why spawning new sessions matters

If `ocha` tried to do everything through one long-lived Junie conversation, it would mix planning, execution, review, and state tracking into one stream.

Spawning separate headless sessions gives cleaner boundaries:

- each session has one job
- prompts stay shorter and more targeted
- logs are easier to attribute
- retries are easier to isolate
- one failed builder does not poison the whole operator session

This is the same reason isolated worktrees matter: isolation makes failure and recovery manageable.

## Required execution boundary: worktree plus role

For `ocha`, a spawned Junie worker should be defined by at least these fields:

- `session_id`
- `role`
- `task_id`
- `worktree_path`
- `branch` = `agent`
- `owned_directory` or module target
- `status`
- `started_at` / `finished_at`

That means the real identity of a worker is not just “agent 3.”

It is something more like:

> reviewer session for task `T-14`, running in `/ocha/agent-3`, validating changes inside `src/lib/worktree.js` while aligned to `agent`

That level of identity makes the TUI much easier to reason about.

## How a headless spawn should conceptually work

`ocha` should treat spawning as a controlled pipeline step.

Conceptual sequence:

1. create or select the target worktree
2. ensure the worktree is aligned with the latest shared branch state
3. assemble the role-specific prompt
4. launch a headless Junie session in that worktree
5. stream stdout/stderr and structured lifecycle events
6. persist state so the TUI can reload it
7. on completion, decide whether to retry, review, sync, or stop

In other words, `ocha` should not think “open another chat.”

It should think “start another managed job with Junie as the engine.”

## Shared branch rule still applies

Even when `ocha` spawns many headless Junie sessions, the branch model stays the same as the rest of these notes:

- one shared branch line: `agent`
- one worktree per active worker
- task partitioning by directory/module when possible
- fetch/rebase before push
- same-file parallel edits should be avoided by scheduling, not normalized as the default workflow

So spawning more Junie sessions does **not** mean creating branch-per-agent complexity.

The concurrency boundary is the worktree and the assigned task scope.

## What the TUI should expose about spawned Junie sessions

If the operator is going to trust headless execution, the TUI should make the hidden session model visible.

Each task or worker row should ideally show:

- Junie role
- current state
- worktree path
- assigned repo area
- branch name (`agent`)
- retry count
- latest summary event

That keeps the system inspectable even though the workers are headless.

## Good mental model

The cleanest mental model is:

- `ocha` is the **orchestrator and dashboard**
- Junie is the **execution engine** used for each role
- worktrees are the **isolation boundary**
- the shared branch `agent` is the **synchronization line**

So when `ocha` “spawns agents,” what it is really doing is spawning **new headless Junie sessions with explicit roles, explicit worktrees, and explicit sync rules**.

## Recommended wording for the project

If you want the docs to stay consistent, describe the runtime like this:

> `ocha` launches headless Junie sessions for coordinator, lead, builder, and reviewer roles. Each active worker runs in its own isolated worktree while sharing the same branch line, `agent`. The TUI is the operator's control surface for watching, selecting, and managing those spawned Junie sessions.