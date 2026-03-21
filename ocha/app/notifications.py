"""Notification primitives for the ocha TUI.

Provides a small notification center that normalises severity, formatting,
and duplicate suppression for transient in-app notifications.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from typing import Callable


class NotificationLevel(StrEnum):
    """Internal severity level for user-facing notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


_LEVEL_ICONS: dict[NotificationLevel, str] = {
    NotificationLevel.INFO: "→",
    NotificationLevel.SUCCESS: "✓",
    NotificationLevel.WARNING: "⚠",
    NotificationLevel.ERROR: "✕",
}

_LEVEL_COLORS: dict[NotificationLevel, str] = {
    NotificationLevel.INFO: "#83a598",
    NotificationLevel.SUCCESS: "#b8bb26",
    NotificationLevel.WARNING: "#fabd2f",
    NotificationLevel.ERROR: "#fb4934",
}

_LEVEL_TO_TEXTUAL_SEVERITY: dict[NotificationLevel, str] = {
    NotificationLevel.INFO: "information",
    NotificationLevel.SUCCESS: "information",
    NotificationLevel.WARNING: "warning",
    NotificationLevel.ERROR: "error",
}


@dataclass(slots=True, frozen=True)
class NotificationEvent:
    """A normalised notification payload."""

    message: str
    level: NotificationLevel = NotificationLevel.INFO
    title: str = ""
    timeout: float | None = None
    dedupe_key: str | None = None

    @property
    def severity(self) -> str:
        """Return Textual severity name expected by ``App.notify``."""

        return _LEVEL_TO_TEXTUAL_SEVERITY[self.level]

    def rich_message(self) -> str:
        """Return Rich-markup text with a level-specific icon."""

        icon = _LEVEL_ICONS[self.level]
        color = _LEVEL_COLORS[self.level]
        return f"[{color}]{icon}[/] {self.message}"


class NotificationCenter:
    """Dispatches app notifications with optional short-window deduping."""

    def __init__(
        self,
        sender: Callable[[NotificationEvent], None],
        *,
        default_timeout: float = 4.0,
        dedupe_window_seconds: float = 1.5,
        max_history: int = 200,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._sender = sender
        self._clock = clock
        self.default_timeout = default_timeout
        self.dedupe_window_seconds = dedupe_window_seconds
        self._recent_keys: deque[tuple[float, str]] = deque()
        self._history: deque[NotificationEvent] = deque(maxlen=max_history)

    @property
    def history(self) -> tuple[NotificationEvent, ...]:
        """Return immutable snapshot of dispatched notifications."""

        return tuple(self._history)

    def emit(
        self,
        message: str,
        *,
        level: NotificationLevel = NotificationLevel.INFO,
        title: str = "",
        timeout: float | None = None,
        dedupe_key: str | None = None,
    ) -> bool:
        """Create and dispatch a notification.

        Returns ``True`` when dispatched, ``False`` when suppressed as a
        short-window duplicate.
        """

        event = NotificationEvent(
            message=message,
            level=level,
            title=title,
            timeout=self.default_timeout if timeout is None else timeout,
            dedupe_key=dedupe_key,
        )
        return self.emit_event(event)

    def emit_event(self, event: NotificationEvent) -> bool:
        """Dispatch a pre-built event."""

        key = self._fingerprint(event)
        now = self._clock()
        self._prune_recent(now)

        if key and any(existing_key == key for _, existing_key in self._recent_keys):
            return False

        if key:
            self._recent_keys.append((now, key))

        self._history.append(event)
        self._sender(event)
        return True

    def info(self, message: str, **kwargs) -> bool:
        return self.emit(message, level=NotificationLevel.INFO, **kwargs)

    def success(self, message: str, **kwargs) -> bool:
        return self.emit(message, level=NotificationLevel.SUCCESS, **kwargs)

    def warning(self, message: str, **kwargs) -> bool:
        return self.emit(message, level=NotificationLevel.WARNING, **kwargs)

    def error(self, message: str, **kwargs) -> bool:
        return self.emit(message, level=NotificationLevel.ERROR, **kwargs)

    def _fingerprint(self, event: NotificationEvent) -> str | None:
        if self.dedupe_window_seconds <= 0:
            return None
        return event.dedupe_key or f"{event.level}|{event.title}|{event.message}"

    def _prune_recent(self, now: float) -> None:
        if self.dedupe_window_seconds <= 0:
            self._recent_keys.clear()
            return
        cutoff = now - self.dedupe_window_seconds
        while self._recent_keys and self._recent_keys[0][0] < cutoff:
            self._recent_keys.popleft()
