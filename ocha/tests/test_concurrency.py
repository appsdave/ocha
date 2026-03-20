"""Tests for the execution-plan computation and concurrency module."""

from __future__ import annotations

import unittest

from app.concurrency import (
    ConcurrencyPolicy,
    ExecutionGroup,
    _owned_patterns,
    _scopes_conflict,
    compute_execution_plan,
)
from app.state import WorkerRole, WorkerSession, WorkerStatus


def _worker(
    session_id: str,
    owned_directory: str,
    status: WorkerStatus = WorkerStatus.QUEUED,
    role: WorkerRole = WorkerRole.BUILDER,
) -> WorkerSession:
    """Create a minimal WorkerSession for testing."""
    return WorkerSession(
        session_id=session_id,
        task_id="T-001",
        title="Test",
        role=role,
        status=status,
        branch="agent",
        worktree_path=f"/tmp/{session_id}",
        owned_directory=owned_directory,
        summary="",
        task_prompt="prompt",
        role_prompt_path="app/roles/builder.md",
        latest_event="",
    )


# ── _owned_patterns ──────────────────────────────────────────────────


class TestOwnedPatterns(unittest.TestCase):
    def test_single_directory(self):
        w = _worker("s1", "app/")
        self.assertEqual(_owned_patterns(w), ["app/"])

    def test_empty_directory(self):
        w = _worker("s1", "")
        self.assertEqual(_owned_patterns(w), [])


# ── _scopes_conflict ─────────────────────────────────────────────────


class TestScopesConflict(unittest.TestCase):
    def test_same_directory_conflicts(self):
        a = _worker("s1", "app/")
        b = _worker("s2", "app/")
        self.assertTrue(_scopes_conflict(a, b))

    def test_disjoint_directories_no_conflict(self):
        a = _worker("s1", "docs/")
        b = _worker("s2", "app/")
        self.assertFalse(_scopes_conflict(a, b))

    def test_parent_child_conflicts(self):
        a = _worker("s1", "app/")
        b = _worker("s2", "app/sub/")
        self.assertTrue(_scopes_conflict(a, b))

    def test_both_empty_no_conflict(self):
        a = _worker("s1", "")
        b = _worker("s2", "")
        self.assertFalse(_scopes_conflict(a, b))

    def test_one_empty_no_conflict(self):
        a = _worker("s1", "app/")
        b = _worker("s2", "")
        self.assertFalse(_scopes_conflict(a, b))


# ── compute_execution_plan ───────────────────────────────────────────


class TestComputeExecutionPlan(unittest.TestCase):
    def test_empty_workers_returns_empty(self):
        plan = compute_execution_plan([])
        self.assertEqual(plan, [])

    def test_no_queued_workers_returns_empty(self):
        w = _worker("s1", "app/", status=WorkerStatus.RUNNING)
        plan = compute_execution_plan([w])
        self.assertEqual(plan, [])

    def test_single_queued_worker(self):
        w = _worker("s1", "app/")
        plan = compute_execution_plan([w])
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 1)
        self.assertIs(plan[0].workers[0], w)

    def test_disjoint_workers_grouped_together(self):
        """Workers with non-overlapping scopes should be in one group."""
        w1 = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        w2 = _worker("s2", "app/", role=WorkerRole.BUILDER)
        plan = compute_execution_plan([w1, w2])
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 2)

    def test_overlapping_workers_in_separate_groups(self):
        """Workers with overlapping scopes must be in different groups."""
        w1 = _worker("s1", "app/", role=WorkerRole.BUILDER)
        w2 = _worker("s2", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([w1, w2])
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 1)
        self.assertEqual(len(plan[1]), 1)

    def test_mixed_scopes_partial_parallelism(self):
        """Three workers: two disjoint + one conflicting → 2 groups."""
        coord = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        builder = _worker("s2", "app/", role=WorkerRole.BUILDER)
        reviewer = _worker("s3", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([coord, builder, reviewer])
        # coord and builder can run together; reviewer conflicts with builder
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 2)  # coord + builder
        self.assertEqual(len(plan[1]), 1)  # reviewer

    def test_sequential_policy(self):
        """SEQUENTIAL policy puts each worker in its own group."""
        w1 = _worker("s1", "docs/")
        w2 = _worker("s2", "app/")
        plan = compute_execution_plan([w1, w2], ConcurrencyPolicy.SEQUENTIAL)
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 1)
        self.assertEqual(len(plan[1]), 1)

    def test_force_parallel_policy(self):
        """FORCE_PARALLEL puts all workers in one group regardless of conflicts."""
        w1 = _worker("s1", "app/")
        w2 = _worker("s2", "app/")
        plan = compute_execution_plan([w1, w2], ConcurrencyPolicy.FORCE_PARALLEL)
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 2)

    def test_skips_non_queued_workers(self):
        """Running and completed workers are ignored."""
        running = _worker("s1", "app/", status=WorkerStatus.RUNNING)
        completed = _worker("s2", "docs/", status=WorkerStatus.COMPLETED)
        queued = _worker("s3", "app/")
        plan = compute_execution_plan([running, completed, queued])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].session_ids, ["s3"])

    def test_four_workers_realistic_pipeline(self):
        """Simulate a realistic ocha pipeline: coord/docs, lead/planning, builder/app, reviewer/app."""
        coord = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        lead = _worker("s2", "planning/", role=WorkerRole.LEAD)
        builder = _worker("s3", "app/", role=WorkerRole.BUILDER)
        reviewer = _worker("s4", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([coord, lead, builder, reviewer])
        # coord, lead, builder all disjoint → group 1
        # reviewer conflicts with builder → group 2
        self.assertEqual(len(plan), 2)
        group1_ids = plan[0].session_ids
        self.assertIn("s1", group1_ids)
        self.assertIn("s2", group1_ids)
        self.assertIn("s3", group1_ids)
        self.assertEqual(plan[1].session_ids, ["s4"])


# ── ExecutionGroup ───────────────────────────────────────────────────


class TestExecutionGroup(unittest.TestCase):
    def test_session_ids(self):
        w1 = _worker("s1", "docs/")
        w2 = _worker("s2", "app/")
        group = ExecutionGroup(workers=(w1, w2))
        self.assertEqual(group.session_ids, ["s1", "s2"])

    def test_len(self):
        w1 = _worker("s1", "docs/")
        group = ExecutionGroup(workers=(w1,))
        self.assertEqual(len(group), 1)


# ── ConcurrencyPolicy enum ──────────────────────────────────────────


class TestConcurrencyPolicy(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ConcurrencyPolicy.SEQUENTIAL, "sequential")
        self.assertEqual(ConcurrencyPolicy.AUTO, "auto")
        self.assertEqual(ConcurrencyPolicy.FORCE_PARALLEL, "parallel")

    def test_is_str_enum(self):
        self.assertIsInstance(ConcurrencyPolicy.AUTO, str)
