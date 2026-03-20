"""Tests for the performance improvements in T-002.

Covers:
- lru_cache on load_role_definitions (orchestrator.py)
- deque-based bounded log buffers (state.py)
- output_lines() result caching on OchaTask (state.py)
"""
from __future__ import annotations

import unittest
from collections import deque

from app.orchestrator import load_role_definitions
from app.state import MAX_LOG_LINES, OchaTask, OutputMode, WorkerRole, WorkerSession, WorkerStatus


def _make_worker(**overrides) -> WorkerSession:
    defaults = dict(
        session_id="S-001-01",
        task_id="T-001",
        title="test",
        role=WorkerRole.COORDINATOR,
        status=WorkerStatus.RUNNING,
        branch="agent",
        worktree_path="/tmp/wt",
        owned_directory="docs/",
        summary="test worker",
    )
    defaults.update(overrides)
    return WorkerSession(**defaults)


def _make_task(workers=None) -> OchaTask:
    if workers is None:
        workers = [_make_worker()]
    return OchaTask(
        task_id="T-001",
        title="perf test",
        user_task="test",
        branch="agent",
        workers=workers,
    )


class TestLoadRoleDefinitionsCache(unittest.TestCase):
    """Verify that load_role_definitions uses lru_cache."""

    def test_returns_same_object_on_repeated_calls(self) -> None:
        first = load_role_definitions()
        second = load_role_definitions()
        self.assertIs(first, second)

    def test_cache_info_shows_hits(self) -> None:
        load_role_definitions()
        load_role_definitions()
        info = load_role_definitions.cache_info()
        self.assertGreater(info.hits, 0)


class TestDequeLogBuffers(unittest.TestCase):
    """Verify WorkerSession uses bounded deque log buffers."""

    def test_workflow_log_is_deque(self) -> None:
        w = _make_worker()
        self.assertIsInstance(w.workflow_log, deque)

    def test_raw_log_is_deque(self) -> None:
        w = _make_worker()
        self.assertIsInstance(w.raw_log, deque)

    def test_workflow_log_has_maxlen(self) -> None:
        w = _make_worker()
        self.assertEqual(w.workflow_log.maxlen, MAX_LOG_LINES)

    def test_raw_log_has_maxlen(self) -> None:
        w = _make_worker()
        self.assertEqual(w.raw_log.maxlen, MAX_LOG_LINES)

    def test_deque_drops_oldest_when_full(self) -> None:
        w = _make_worker()
        for i in range(MAX_LOG_LINES + 100):
            w.workflow_log.append(f"line-{i}")
        self.assertEqual(len(w.workflow_log), MAX_LOG_LINES)
        # Oldest lines should have been evicted
        self.assertEqual(w.workflow_log[0], "line-100")
        self.assertEqual(w.workflow_log[-1], f"line-{MAX_LOG_LINES + 99}")

    def test_append_works_normally_under_limit(self) -> None:
        w = _make_worker()
        w.workflow_log.append("hello")
        w.raw_log.append("world")
        self.assertEqual(list(w.workflow_log), ["hello"])
        self.assertEqual(list(w.raw_log), ["world"])


class TestOutputLinesCache(unittest.TestCase):
    """Verify output_lines() caches results and invalidates on change."""

    def test_repeated_calls_return_same_list(self) -> None:
        task = _make_task()
        task.workers[0].workflow_log.append("event one")
        first = task.output_lines(OutputMode.WORKFLOW)
        second = task.output_lines(OutputMode.WORKFLOW)
        self.assertIs(first, second)

    def test_cache_invalidates_on_new_log_entry(self) -> None:
        task = _make_task()
        task.workers[0].workflow_log.append("event one")
        first = task.output_lines(OutputMode.WORKFLOW)
        task.workers[0].workflow_log.append("event two")
        second = task.output_lines(OutputMode.WORKFLOW)
        self.assertIsNot(first, second)
        self.assertEqual(len(second), 2)

    def test_cache_differs_by_mode(self) -> None:
        task = _make_task()
        task.workers[0].workflow_log.append("wf")
        task.workers[0].raw_log.append("raw")
        wf = task.output_lines(OutputMode.WORKFLOW)
        raw = task.output_lines(OutputMode.RAW)
        self.assertNotEqual(wf, raw)

    def test_output_lines_formats_correctly(self) -> None:
        task = _make_task()
        task.workers[0].workflow_log.append("hello")
        lines = task.output_lines(OutputMode.WORKFLOW)
        self.assertEqual(lines, ["[coordinator] hello"])


if __name__ == "__main__":
    unittest.main()
