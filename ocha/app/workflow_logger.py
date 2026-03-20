"""Structured workflow logging for ocha task pipelines.

Provides timestamped, levelled, categorised log entries that replace
the plain-string ``workflow_log`` lists used previously.  Every entry
carries enough metadata for the TUI to render rich output (icons,
colours, filtering) while remaining serialisable to plain text for
raw-mode display and persistence.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Iterator, Sequence


# ── Log levels ────────────────────────────────────────────────────────

class LogLevel(StrEnum):
    """Severity / importance of a workflow log entry."""
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


LEVEL_ICONS: dict[LogLevel, str] = {
    LogLevel.DEBUG: "·",
    LogLevel.INFO: "→",
    LogLevel.SUCCESS: "✓",
    LogLevel.WARNING: "⚠",
    LogLevel.ERROR: "✕",
}

LEVEL_COLORS: dict[LogLevel, str] = {
    LogLevel.DEBUG: "#928374",
    LogLevel.INFO: "#83a598",
    LogLevel.SUCCESS: "#b8bb26",
    LogLevel.WARNING: "#fabd2f",
    LogLevel.ERROR: "#fb4934",
}


# ── Event categories ─────────────────────────────────────────────────

class EventCategory(StrEnum):
    """Broad category for a workflow event — drives TUI grouping."""
    LIFECYCLE = "lifecycle"       # worker start / stop / kill
    PIPELINE = "pipeline"        # phase advance, upstream handoff
    GIT = "git"                  # worktree, commit, push, PR
    JUNIE = "junie"              # junie process spawn / output / exit
    PROMPT = "prompt"            # prompt build, truncation
    SYSTEM = "system"            # fallback / internal


# ── Log entry ─────────────────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class LogEntry:
    """A single structured workflow log entry."""
    timestamp: datetime
    level: LogLevel
    category: EventCategory
    message: str
    role: str = ""
    session_id: str = ""

    # ── Formatters ────────────────────────────────────────────────────

    def plain(self) -> str:
        """Return a plain-text representation (for raw log / persistence)."""
        ts = self.timestamp.strftime("%H:%M:%S")
        icon = LEVEL_ICONS[self.level]
        prefix = f"[{self.role}] " if self.role else ""
        return f"{ts} {icon} {prefix}{self.message}"

    def rich(self) -> str:
        """Return a Textual Rich-markup string for TUI rendering."""
        ts = self.timestamp.strftime("%H:%M:%S")
        icon = LEVEL_ICONS[self.level]
        color = LEVEL_COLORS[self.level]
        cat_tag = f"[#504945]{self.category}[/] " if self.category != EventCategory.SYSTEM else ""
        prefix = f"\\[{self.role}] " if self.role else ""
        return f"[#665c54]{ts}[/] [{color}]{icon}[/] {cat_tag}{prefix}{self.message}"


# ── Maximum retained entries per logger (mirrors MAX_LOG_LINES) ──────

MAX_WORKFLOW_ENTRIES = 5_000


# ── WorkflowLogger ───────────────────────────────────────────────────

class WorkflowLogger:
    """Accumulates structured :class:`LogEntry` items for a single worker.

    The logger is the single place where workflow log lines are created.
    Callers use the convenience helpers (:meth:`info`, :meth:`success`, …)
    instead of appending raw strings — ensuring every entry is timestamped
    and categorised.

    For backwards compatibility the logger also writes a plain-text copy
    into an optional legacy ``deque[str]`` so existing widgets that read
    ``worker.workflow_log`` keep working during migration.
    """

    def __init__(
        self,
        role: str = "",
        session_id: str = "",
        legacy_deque: deque[str] | None = None,
        maxlen: int = MAX_WORKFLOW_ENTRIES,
    ) -> None:
        self.role = role
        self.session_id = session_id
        self.entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._legacy: deque[str] | None = legacy_deque

    # ── Core append ───────────────────────────────────────────────────

    def log(
        self,
        level: LogLevel,
        message: str,
        category: EventCategory = EventCategory.SYSTEM,
    ) -> LogEntry:
        """Create, store, and return a new :class:`LogEntry`."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            role=self.role,
            session_id=self.session_id,
        )
        self.entries.append(entry)
        if self._legacy is not None:
            self._legacy.append(entry.plain())
        return entry

    # ── Convenience helpers ───────────────────────────────────────────

    def debug(self, message: str, category: EventCategory = EventCategory.SYSTEM) -> LogEntry:
        return self.log(LogLevel.DEBUG, message, category)

    def info(self, message: str, category: EventCategory = EventCategory.SYSTEM) -> LogEntry:
        return self.log(LogLevel.INFO, message, category)

    def success(self, message: str, category: EventCategory = EventCategory.SYSTEM) -> LogEntry:
        return self.log(LogLevel.SUCCESS, message, category)

    def warning(self, message: str, category: EventCategory = EventCategory.SYSTEM) -> LogEntry:
        return self.log(LogLevel.WARNING, message, category)

    def error(self, message: str, category: EventCategory = EventCategory.SYSTEM) -> LogEntry:
        return self.log(LogLevel.ERROR, message, category)

    # ── Lifecycle shortcuts ───────────────────────────────────────────

    def lifecycle(self, message: str, level: LogLevel = LogLevel.INFO) -> LogEntry:
        return self.log(level, message, EventCategory.LIFECYCLE)

    def pipeline(self, message: str, level: LogLevel = LogLevel.INFO) -> LogEntry:
        return self.log(level, message, EventCategory.PIPELINE)

    def git(self, message: str, level: LogLevel = LogLevel.INFO) -> LogEntry:
        return self.log(level, message, EventCategory.GIT)

    def junie(self, message: str, level: LogLevel = LogLevel.INFO) -> LogEntry:
        return self.log(level, message, EventCategory.JUNIE)

    def prompt(self, message: str, level: LogLevel = LogLevel.INFO) -> LogEntry:
        return self.log(level, message, EventCategory.PROMPT)

    # ── Filtering ─────────────────────────────────────────────────────

    def filter(
        self,
        *,
        level: LogLevel | None = None,
        min_level: LogLevel | None = None,
        category: EventCategory | None = None,
    ) -> list[LogEntry]:
        """Return entries matching the given filters.

        *level* selects a single exact level.  *min_level* selects that
        level and all higher-severity levels (uses the ordering
        ``DEBUG < INFO < SUCCESS < WARNING < ERROR``).  *category*
        restricts to a single event category.  All filters that are set
        are combined with AND logic.
        """
        severity_order: list[LogLevel] = [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.SUCCESS,
            LogLevel.WARNING,
            LogLevel.ERROR,
        ]
        result: list[LogEntry] = []
        for entry in self.entries:
            if level is not None and entry.level != level:
                continue
            if min_level is not None:
                if severity_order.index(entry.level) < severity_order.index(min_level):
                    continue
            if category is not None and entry.category != category:
                continue
            result.append(entry)
        return result

    # ── Bulk access ───────────────────────────────────────────────────

    def plain_lines(self) -> list[str]:
        """Return all entries as plain-text lines."""
        return [e.plain() for e in self.entries]

    def rich_lines(self) -> list[str]:
        """Return all entries as Textual Rich-markup lines."""
        return [e.rich() for e in self.entries]

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def __iter__(self) -> Iterator[LogEntry]:
        return iter(self.entries)


# ── Factory helper ────────────────────────────────────────────────────

def make_logger(
    role: str,
    session_id: str,
    legacy_deque: deque[str] | None = None,
) -> WorkflowLogger:
    """Create a :class:`WorkflowLogger` pre-configured for a worker."""
    return WorkflowLogger(
        role=role,
        session_id=session_id,
        legacy_deque=legacy_deque,
    )
