<<<<<<< HEAD
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
=======
"""Tests for the multi-agent concurrency features.

Covers:
- ``can_run_parallel`` graph-colouring algorithm
- ``compute_execution_plan`` orchestrator function
- ``ConcurrencyPolicy`` and ``ExecutionGroup`` data types
- Atomic file-lock operations under concurrent access
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from app.file_lock import can_run_parallel
from app.orchestrator import compute_execution_plan
from app.state import ConcurrencyPolicy, ExecutionGroup, WorkerRole, WorkerSession, WorkerStatus


# ── Helpers ──────────────────────────────────────────────────────────

def _make_worker(
    session_id: str,
    role: WorkerRole,
    owned_directory: str,
    status: WorkerStatus = WorkerStatus.QUEUED,
) -> WorkerSession:
    return WorkerSession(
        session_id=session_id,
        task_id="T-001",
        title="Test task",
        role=role,
        status=status,
        branch="agent",
        worktree_path=f"/tmp/wt-{session_id}",
        owned_directory=owned_directory,
        summary="test",
    )


# ── can_run_parallel ─────────────────────────────────────────────────


class TestCanRunParallel:
    def test_empty_workers(self):
        assert can_run_parallel([]) == []

    def test_single_worker(self):
        result = can_run_parallel([("s1", "coordinator", ["docs/"])])
        assert result == [[0]]

    def test_all_disjoint(self):
        workers = [
            ("s1", "coordinator", ["docs/"]),
            ("s2", "lead", ["planning/"]),
            ("s3", "builder", ["app/"]),
        ]
        result = can_run_parallel(workers)
        # All can run in one group
        assert len(result) == 1
        assert sorted(result[0]) == [0, 1, 2]

    def test_overlapping_pair_serialised(self):
        workers = [
            ("s1", "coordinator", ["docs/"]),
            ("s2", "lead", ["planning/"]),
            ("s3", "builder", ["app/"]),
            ("s4", "reviewer", ["app/"]),
        ]
        result = can_run_parallel(workers)
        # builder and reviewer conflict → need at least 2 groups
        assert len(result) == 2
        # First group has coordinator, lead, builder (or reviewer)
        assert 0 in result[0]  # coordinator
        assert 1 in result[0]  # lead
        # builder and reviewer in different groups
        builder_group = next(g for g in range(len(result)) if 2 in result[g])
        reviewer_group = next(g for g in range(len(result)) if 3 in result[g])
        assert builder_group != reviewer_group

    def test_all_same_directory(self):
        workers = [
            ("s1", "a", ["app/"]),
            ("s2", "b", ["app/"]),
            ("s3", "c", ["app/"]),
        ]
        result = can_run_parallel(workers)
        # Each must be in its own group
        assert len(result) == 3
        for group in result:
            assert len(group) == 1

    def test_two_disjoint_pairs(self):
        workers = [
            ("s1", "a", ["docs/"]),
            ("s2", "b", ["docs/"]),
            ("s3", "c", ["app/"]),
            ("s4", "d", ["app/"]),
        ]
        result = can_run_parallel(workers)
        # Two groups: [docs-1, app-1] and [docs-2, app-2]
        assert len(result) == 2
        for group in result:
            assert len(group) == 2
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)


# ── compute_execution_plan ───────────────────────────────────────────


<<<<<<< HEAD
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
=======
class TestComputeExecutionPlan:
    def _default_workers(self) -> list[WorkerSession]:
        return [
            _make_worker("s1", WorkerRole.COORDINATOR, "docs/"),
            _make_worker("s2", WorkerRole.LEAD, "planning/"),
            _make_worker("s3", WorkerRole.BUILDER, "app/"),
            _make_worker("s4", WorkerRole.REVIEWER, "app/"),
        ]

    def test_sequential_policy(self):
        workers = self._default_workers()
        plan = compute_execution_plan(workers, ConcurrencyPolicy.SEQUENTIAL)
        assert len(plan) == 4
        for i, group in enumerate(plan):
            assert group.group_index == i
            assert group.worker_indices == [i]

    def test_parallel_policy(self):
        workers = self._default_workers()
        plan = compute_execution_plan(workers, ConcurrencyPolicy.PARALLEL)
        assert len(plan) == 1
        assert sorted(plan[0].worker_indices) == [0, 1, 2, 3]

    def test_auto_policy_groups_correctly(self):
        workers = self._default_workers()
        plan = compute_execution_plan(workers, ConcurrencyPolicy.AUTO)
        # coordinator(docs/), lead(planning/), builder(app/) can be parallel
        # reviewer(app/) conflicts with builder → separate group
        assert len(plan) == 2
        # First group should have 3 workers
        assert len(plan[0].worker_indices) == 3
        # Second group should have reviewer
        assert len(plan[1].worker_indices) == 1
        assert 3 in plan[1].worker_indices

    def test_auto_all_disjoint(self):
        workers = [
            _make_worker("s1", WorkerRole.COORDINATOR, "docs/"),
            _make_worker("s2", WorkerRole.LEAD, "planning/"),
            _make_worker("s3", WorkerRole.BUILDER, "app/"),
        ]
        plan = compute_execution_plan(workers, ConcurrencyPolicy.AUTO)
        assert len(plan) == 1
        assert sorted(plan[0].worker_indices) == [0, 1, 2]

    def test_empty_workers(self):
        plan = compute_execution_plan([], ConcurrencyPolicy.AUTO)
        assert plan == []

    def test_execution_group_frozen(self):
        group = ExecutionGroup(group_index=0, worker_indices=[0, 1])
        assert group.group_index == 0
        assert group.worker_indices == [0, 1]
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)


# ── ConcurrencyPolicy enum ──────────────────────────────────────────


<<<<<<< HEAD
class TestConcurrencyPolicy(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ConcurrencyPolicy.SEQUENTIAL, "sequential")
        self.assertEqual(ConcurrencyPolicy.AUTO, "auto")
        self.assertEqual(ConcurrencyPolicy.FORCE_PARALLEL, "parallel")

    def test_is_str_enum(self):
        self.assertIsInstance(ConcurrencyPolicy.AUTO, str)
=======
class TestConcurrencyPolicy:
    def test_values(self):
        assert ConcurrencyPolicy.SEQUENTIAL == "sequential"
        assert ConcurrencyPolicy.PARALLEL == "parallel"
        assert ConcurrencyPolicy.AUTO == "auto"

    def test_from_string(self):
        assert ConcurrencyPolicy("auto") == ConcurrencyPolicy.AUTO
        assert ConcurrencyPolicy("sequential") == ConcurrencyPolicy.SEQUENTIAL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            ConcurrencyPolicy("invalid")


# ── Atomic lock operations ───────────────────────────────────────────


class TestAtomicLockOperations:
    """Verify that acquire/release use the atomic lock path."""

    def test_concurrent_acquire_no_corruption(self, tmp_path: Path):
        """Simulate sequential rapid acquisitions and verify registry integrity."""
        from app.file_lock import acquire_lock, load_locks

        for i in range(10):
            acquire_lock(tmp_path, f"s-{i}", "t1", "role", [f"dir{i}/"])

        locks = load_locks(tmp_path)
        assert len(locks) == 10
        session_ids = {lock.session_id for lock in locks}
        assert len(session_ids) == 10

    def test_sentinel_file_created(self, tmp_path: Path):
        """The .lock sentinel file should exist after acquire."""
        from app.file_lock import acquire_lock

        acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        sentinel = tmp_path / ".ocha" / "locks.lock"
        assert sentinel.exists()
>>>>>>> b2d8e34 (ocha: coordinator S-003-01)
