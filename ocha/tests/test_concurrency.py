"""Tests for the execution-plan computation and concurrency helpers."""

from __future__ import annotations

from pathlib import Path
import unittest

import pytest

from app.concurrency import (
    ConcurrencyPolicy,
    ExecutionGroup,
    _owned_patterns,
    _scopes_conflict,
    compute_execution_plan,
)
from app.file_lock import acquire_lock, can_run_parallel, load_locks
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


class TestOwnedPatterns(unittest.TestCase):
    def test_single_directory(self):
        worker = _worker("s1", "app/")
        self.assertEqual(_owned_patterns(worker), ["app/"])

    def test_empty_directory(self):
        worker = _worker("s1", "")
        self.assertEqual(_owned_patterns(worker), [])


class TestScopesConflict(unittest.TestCase):
    def test_same_directory_conflicts(self):
        self.assertTrue(_scopes_conflict(_worker("s1", "app/"), _worker("s2", "app/")))

    def test_disjoint_directories_no_conflict(self):
        self.assertFalse(_scopes_conflict(_worker("s1", "docs/"), _worker("s2", "app/")))

    def test_parent_child_conflicts(self):
        self.assertTrue(_scopes_conflict(_worker("s1", "app/"), _worker("s2", "app/sub/")))

    def test_both_empty_no_conflict(self):
        self.assertFalse(_scopes_conflict(_worker("s1", ""), _worker("s2", "")))

    def test_one_empty_no_conflict(self):
        self.assertFalse(_scopes_conflict(_worker("s1", "app/"), _worker("s2", "")))


class TestCanRunParallel:
    def test_empty_workers(self):
        assert can_run_parallel([]) == []

    def test_single_worker(self):
        assert can_run_parallel([("s1", "coordinator", ["docs/"])]) == [[0]]

    def test_all_disjoint(self):
        workers = [
            ("s1", "coordinator", ["docs/"]),
            ("s2", "lead", ["planning/"]),
            ("s3", "builder", ["app/"]),
        ]
        result = can_run_parallel(workers)
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
        assert len(result) == 2
        assert 0 in result[0]
        assert 1 in result[0]
        builder_group = next(index for index, group in enumerate(result) if 2 in group)
        reviewer_group = next(index for index, group in enumerate(result) if 3 in group)
        assert builder_group != reviewer_group

    def test_all_same_directory(self):
        workers = [
            ("s1", "a", ["app/"]),
            ("s2", "b", ["app/"]),
            ("s3", "c", ["app/"]),
        ]
        result = can_run_parallel(workers)
        assert len(result) == 3
        assert all(len(group) == 1 for group in result)

    def test_two_disjoint_pairs(self):
        workers = [
            ("s1", "a", ["docs/"]),
            ("s2", "b", ["docs/"]),
            ("s3", "c", ["app/"]),
            ("s4", "d", ["app/"]),
        ]
        result = can_run_parallel(workers)
        assert len(result) == 2
        assert all(len(group) == 2 for group in result)


class TestComputeExecutionPlan(unittest.TestCase):
    def test_empty_workers_returns_empty(self):
        self.assertEqual(compute_execution_plan([]), [])

    def test_no_queued_workers_returns_empty(self):
        worker = _worker("s1", "app/", status=WorkerStatus.RUNNING)
        self.assertEqual(compute_execution_plan([worker]), [])

    def test_single_queued_worker(self):
        worker = _worker("s1", "app/")
        plan = compute_execution_plan([worker])
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 1)
        self.assertIs(plan[0].workers[0], worker)

    def test_disjoint_workers_grouped_together(self):
        coord = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        builder = _worker("s2", "app/", role=WorkerRole.BUILDER)
        plan = compute_execution_plan([coord, builder])
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 2)

    def test_overlapping_workers_in_separate_groups(self):
        builder = _worker("s1", "app/", role=WorkerRole.BUILDER)
        reviewer = _worker("s2", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([builder, reviewer])
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 1)
        self.assertEqual(len(plan[1]), 1)

    def test_mixed_scopes_partial_parallelism(self):
        coord = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        builder = _worker("s2", "app/", role=WorkerRole.BUILDER)
        reviewer = _worker("s3", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([coord, builder, reviewer])
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 2)
        self.assertEqual(len(plan[1]), 1)

    def test_sequential_policy(self):
        plan = compute_execution_plan(
            [_worker("s1", "docs/"), _worker("s2", "app/")],
            ConcurrencyPolicy.SEQUENTIAL,
        )
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]), 1)
        self.assertEqual(len(plan[1]), 1)

    def test_force_parallel_policy(self):
        plan = compute_execution_plan(
            [_worker("s1", "app/"), _worker("s2", "app/")],
            ConcurrencyPolicy.FORCE_PARALLEL,
        )
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]), 2)

    def test_skips_non_queued_workers(self):
        running = _worker("s1", "app/", status=WorkerStatus.RUNNING)
        completed = _worker("s2", "docs/", status=WorkerStatus.COMPLETED)
        queued = _worker("s3", "app/")
        plan = compute_execution_plan([running, completed, queued])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].session_ids, ["s3"])

    def test_four_workers_realistic_pipeline(self):
        coord = _worker("s1", "docs/", role=WorkerRole.COORDINATOR)
        lead = _worker("s2", "planning/", role=WorkerRole.LEAD)
        builder = _worker("s3", "app/", role=WorkerRole.BUILDER)
        reviewer = _worker("s4", "app/", role=WorkerRole.REVIEWER)
        plan = compute_execution_plan([coord, lead, builder, reviewer])
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[1].session_ids, ["s4"])
        self.assertCountEqual(plan[0].session_ids, ["s1", "s2", "s3"])


class TestExecutionGroup(unittest.TestCase):
    def test_session_ids(self):
        group = ExecutionGroup(workers=(_worker("s1", "docs/"), _worker("s2", "app/")))
        self.assertEqual(group.session_ids, ["s1", "s2"])

    def test_len(self):
        group = ExecutionGroup(workers=(_worker("s1", "docs/"),))
        self.assertEqual(len(group), 1)


class TestConcurrencyPolicy(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ConcurrencyPolicy.SEQUENTIAL, "sequential")
        self.assertEqual(ConcurrencyPolicy.AUTO, "auto")
        self.assertEqual(ConcurrencyPolicy.FORCE_PARALLEL, "parallel")

    def test_is_str_enum(self):
        self.assertIsInstance(ConcurrencyPolicy.AUTO, str)


def test_invalid_policy_string_raises() -> None:
    with pytest.raises(ValueError):
        ConcurrencyPolicy("invalid")


class TestAtomicLockOperations:
    def test_concurrent_acquire_no_corruption(self, tmp_path: Path):
        for index in range(10):
            acquire_lock(tmp_path, f"s-{index}", "t1", "role", [f"dir{index}/"])

        locks = load_locks(tmp_path)
        assert len(locks) == 10
        assert {lock.session_id for lock in locks} == {f"s-{index}" for index in range(10)}

    def test_sentinel_file_created(self, tmp_path: Path):
        acquire_lock(tmp_path, "s1", "t1", "coord", ["docs/"])
        assert (tmp_path / ".ocha" / "locks.lock").exists()
