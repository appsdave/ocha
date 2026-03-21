"""Rich ANSI-colored formatting for ``ocha update`` output."""

from __future__ import annotations

from .install import UpdateChangelog

# ANSI escape helpers --------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"

_MAX_FILES_SHOWN = 15


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _status_badge(status: str) -> str:
    """Return a colored badge for a file status."""
    if status == "added":
        return f"{_GREEN}[+]{_RESET}"
    if status == "deleted":
        return f"{_RED}[-]{_RESET}"
    if status == "renamed":
        return f"{_MAGENTA}[R]{_RESET}"
    return f"{_YELLOW}[~]{_RESET}"


def _bar(insertions: int, deletions: int, *, width: int = 20) -> str:
    """Build a mini +/- bar like git diff --stat."""
    total = insertions + deletions
    if total == 0:
        return ""
    scale = min(total, width)
    plus_cols = round(insertions / total * scale) if total else 0
    minus_cols = scale - plus_cols
    return f"{_GREEN}{'+'*plus_cols}{_RED}{'-'*minus_cols}{_RESET}"


def format_update_log(changelog: UpdateChangelog | None, *, repo_url: str = "", target: str = "") -> str:
    """Return a rich, multi-line ANSI-colored update summary.

    If *changelog* is ``None`` (no changes), returns a short
    "already up to date" message.
    """
    if changelog is None:
        return f"{_DIM}Already up to date.{_RESET}"

    lines: list[str] = []

    # Header
    short_old = changelog.previous_revision[:8]
    short_new = changelog.revision[:8]
    lines.append(f"{_BOLD}ocha updated successfully{_RESET}")
    lines.append(
        f"  {_CYAN}{changelog.branch}{_RESET}  "
        f"{_DIM}{short_old}{_RESET} → {_BOLD}{short_new}{_RESET}"
    )
    if repo_url:
        lines.append(f"  {_DIM}{repo_url}{_RESET}")
    lines.append("")

    # Commits
    if changelog.commits:
        lines.append(f"{_BOLD}Commits ({len(changelog.commits)}):{_RESET}")
        for commit in changelog.commits:
            lines.append(f"  {_YELLOW}•{_RESET} {commit}")
        lines.append("")

    # Summary counts
    parts: list[str] = []
    if changelog.files_added:
        parts.append(f"{_GREEN}{_plural(changelog.files_added, 'file')} added{_RESET}")
    if changelog.files_modified:
        parts.append(f"{_YELLOW}{_plural(changelog.files_modified, 'file')} modified{_RESET}")
    if changelog.files_deleted:
        parts.append(f"{_RED}{_plural(changelog.files_deleted, 'file')} deleted{_RESET}")
    if parts:
        lines.append(f"{_BOLD}Files changed:{_RESET} {', '.join(parts)}")

    total_files = len(changelog.file_stats)
    ins = changelog.total_insertions
    dels = changelog.total_deletions
    lines.append(
        f"  {_GREEN}+{ins}{_RESET} / {_RED}-{dels}{_RESET} "
        f"across {_plural(total_files, 'file')}"
    )
    lines.append("")

    # Per-file details
    if changelog.file_stats:
        shown = changelog.file_stats[:_MAX_FILES_SHOWN]
        remaining = total_files - len(shown)
        for fs in shown:
            badge = _status_badge(fs.status)
            bar = _bar(fs.insertions, fs.deletions)
            stat_text = f"{_GREEN}+{fs.insertions}{_RESET}/{_RED}-{fs.deletions}{_RESET}"
            lines.append(f"  {badge} {fs.path}  {stat_text} {bar}")
        if remaining > 0:
            lines.append(f"  {_DIM}… and {_plural(remaining, 'more file')}{_RESET}")

    return "\n".join(lines)
