"""Tests for the structured workflow logger."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from app.workflow_logger import (
    EventCategory,
    LogEntry,
    LogLevel,
    WorkflowLogger,
    make_logger,
)


class TestLogEntry:
    def test_plain_format_includes_timestamp_and_icon(self):
        entry = LogEntry(
            timestamp=datetime(2026, 3, 20, 14, 5, 30),
            level=LogLevel.INFO,
            category=EventCategory.LIFECYCLE,
            message="Worker started.",
        )
        plain = entry.plain()
        assert "14:05:30" in plain
        assert "→" in plain
        assert "Worker started." in plain

    def test_plain_format_with_role(self):
        entry = LogEntry(
            timestamp=datetime(2026, 1, 1, 0, 0, 0),
            level=LogLevel.SUCCESS,
            category=EventCategory.GIT,
            message="Committed.",
            role="builder",
        )
        plain = entry.plain()
        assert "[builder]" in plain
        assert "✓" in plain

    def test_rich_format_includes_markup(self):
        entry = LogEntry(
            timestamp=datetime(2026, 3, 20, 9, 0, 0),
            level=LogLevel.ERROR,
            category=EventCategory.JUNIE,
            message="Process crashed.",
            role="coordinator",
        )
        rich = entry.rich()
        assert "#fb4934" in rich  # error colour
        assert "✕" in rich
        assert "Process crashed." in rich
        assert "junie" in rich  # category tag

    def test_rich_format_omits_system_category_tag(self):
        entry = LogEntry(
            timestamp=datetime(2026, 1, 1, 0, 0, 0),
            level=LogLevel.DEBUG,
            category=EventCategory.SYSTEM,
            message="Internal.",
        )
        rich = entry.rich()
        assert "system" not in rich


class TestWorkflowLogger:
    def test_convenience_methods_set_correct_level(self):
        logger = WorkflowLogger(role="lead", session_id="S-001-02")
        logger.debug("d")
        logger.info("i")
        logger.success("s")
        logger.warning("w")
        logger.error("e")
        levels = [e.level for e in logger.entries]
        assert levels == [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.SUCCESS,
            LogLevel.WARNING,
            LogLevel.ERROR,
        ]

    def test_category_shortcuts(self):
        logger = WorkflowLogger()
        logger.lifecycle("a")
        logger.pipeline("b")
        logger.git("c")
        logger.junie("d")
        logger.prompt("e")
        cats = [e.category for e in logger.entries]
        assert cats == [
            EventCategory.LIFECYCLE,
            EventCategory.PIPELINE,
            EventCategory.GIT,
            EventCategory.JUNIE,
            EventCategory.PROMPT,
        ]

    def test_legacy_deque_sync(self):
        legacy: deque[str] = deque(maxlen=100)
        logger = WorkflowLogger(role="builder", session_id="S-001-03", legacy_deque=legacy)
        logger.info("hello world")
        assert len(legacy) == 1
        assert "hello world" in legacy[0]

    def test_maxlen_respected(self):
        logger = WorkflowLogger(maxlen=3)
        for i in range(5):
            logger.info(f"msg-{i}")
        assert len(logger) == 3
        messages = [e.message for e in logger.entries]
        assert messages == ["msg-2", "msg-3", "msg-4"]

    def test_plain_lines_and_rich_lines(self):
        logger = WorkflowLogger(role="reviewer", session_id="S-001-04")
        logger.success("All good.", EventCategory.LIFECYCLE)
        logger.error("Oops.", EventCategory.JUNIE)
        plains = logger.plain_lines()
        richs = logger.rich_lines()
        assert len(plains) == 2
        assert len(richs) == 2
        # Plain lines should NOT contain rich markup brackets for colours
        for line in plains:
            assert "#b8bb26" not in line
        # Rich lines should contain colour markup
        assert any("#b8bb26" in line for line in richs)

    def test_bool_and_len(self):
        logger = WorkflowLogger()
        assert not logger
        assert len(logger) == 0
        logger.info("x")
        assert logger
        assert len(logger) == 1

    def test_entries_carry_role_and_session(self):
        logger = WorkflowLogger(role="coordinator", session_id="S-001-01")
        entry = logger.info("test")
        assert entry.role == "coordinator"
        assert entry.session_id == "S-001-01"


class TestMakeLogger:
    def test_factory_returns_configured_logger(self):
        legacy: deque[str] = deque(maxlen=100)
        logger = make_logger("builder", "S-002-03", legacy_deque=legacy)
        assert logger.role == "builder"
        assert logger.session_id == "S-002-03"
        logger.git("committed")
        assert len(legacy) == 1
