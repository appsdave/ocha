"""Tests for app notification primitives."""

from __future__ import annotations

from app.notifications import NotificationCenter, NotificationEvent, NotificationLevel


def test_notification_event_severity_mapping_and_rich_message() -> None:
    event = NotificationEvent("Task launched", level=NotificationLevel.SUCCESS)
    assert event.severity == "information"
    rich = event.rich_message()
    assert "✓" in rich
    assert "#b8bb26" in rich
    assert "Task launched" in rich


def test_notification_center_deduplicates_within_window() -> None:
    sent: list[NotificationEvent] = []
    now = [10.0]

    center = NotificationCenter(sent.append, dedupe_window_seconds=2.0, clock=lambda: now[0])

    assert center.warning("JUNIE_API_KEY missing", dedupe_key="missing-key")
    assert not center.warning("JUNIE_API_KEY missing", dedupe_key="missing-key")
    assert len(sent) == 1

    now[0] = 13.5
    assert center.warning("JUNIE_API_KEY missing", dedupe_key="missing-key")
    assert len(sent) == 2


def test_notification_center_history_contains_only_dispatched_events() -> None:
    sent: list[NotificationEvent] = []
    center = NotificationCenter(sent.append, dedupe_window_seconds=10.0)

    center.info("one")
    center.info("one")  # duplicate within dedupe window
    center.error("two")

    assert len(center.history) == 2
    assert [e.message for e in center.history] == ["one", "two"]
