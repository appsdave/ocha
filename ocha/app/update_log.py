"""Format rich update logs for the CLI update command."""
from __future__ import annotations

from .install import InstallResult, UpdateChangelog

# ANSI helpers — gracefully degrade if the terminal doesn't support colour.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"

_STATUS_LABELS = {
    "A": f"{_GREEN}added{_RESET}",
    "M": f"{_YELLOW}modified{_RESET}",
    "D": f"{_RED}deleted{_RESET}",
    "R": f"{_CYAN}renamed{_RESET}",
}

_STATUS_ICONS = {
    "A": f"{_GREEN}+{_RESET}",
    "M": f"{_YELLOW}~{_RESET}",
    "D": f"{_RED}-{_RESET}",
    "R": f"{_CYAN}→{_RESET}",
}


def format_update_log(result: InstallResult) -> str:
    """Return a human-friendly multi-line update log string."""
    lines: list[str] = []

    if not result.changed:
        lines.append(f"\n{_BOLD}ocha is already up to date.{_RESET}")
        lines.append(f"  revision {_DIM}{result.revision[:10]}{_RESET} on {_CYAN}{result.branch}{_RESET}")
        return "\n".join(lines)

    # Header
    lines.append("")
    lines.append(f"{_BOLD}━━━ ocha updated successfully ━━━{_RESET}")
    lines.append("")

    # Revision info
    prev_short = (result.previous_revision or "unknown")[:10]
    new_short = result.revision[:10]
    lines.append(f"  {_DIM}branch:{_RESET}   {_CYAN}{result.branch}{_RESET}")
    lines.append(f"  {_DIM}before:{_RESET}   {prev_short}")
    lines.append(f"  {_DIM}after:{_RESET}    {_BOLD}{new_short}{_RESET}")
    lines.append("")

    changelog = result.changelog
    if changelog is None:
        # Fallback to old-style summary
        if result.change_summary:
            lines.append(f"{_BOLD}Changes:{_RESET}")
            for entry in result.change_summary:
                lines.append(f"  • {entry}")
        return "\n".join(lines)

    # Commits section
    if changelog.commits:
        count = len(changelog.commits)
        lines.append(f"{_BOLD}Commits ({count}):{_RESET}")
        for commit in changelog.commits:
            hash_part, _, subject = commit.partition(" ")
            lines.append(f"  {_BLUE}{hash_part}{_RESET} {subject}")
        lines.append("")

    # File overview
    parts = []
    if changelog.files_added:
        parts.append(f"{_GREEN}{changelog.files_added} added{_RESET}")
    if changelog.files_modified:
        parts.append(f"{_YELLOW}{changelog.files_modified} modified{_RESET}")
    if changelog.files_deleted:
        parts.append(f"{_RED}{changelog.files_deleted} deleted{_RESET}")
    if parts:
        lines.append(f"{_BOLD}Files changed:{_RESET} {', '.join(parts)}")

    # Insertion / deletion summary
    if changelog.total_insertions or changelog.total_deletions:
        lines.append(
            f"  {_GREEN}+{changelog.total_insertions}{_RESET}  "
            f"{_RED}-{changelog.total_deletions}{_RESET} lines"
        )
    lines.append("")

    # Per-file detail (top 15)
    if changelog.file_stats:
        shown = changelog.file_stats[:15]
        lines.append(f"{_BOLD}Changed files:{_RESET}")
        for fs in shown:
            icon = _STATUS_ICONS.get(fs.status, " ")
            stat = ""
            if fs.insertions or fs.deletions:
                stat = f" ({_GREEN}+{fs.insertions}{_RESET}/{_RED}-{fs.deletions}{_RESET})"
            lines.append(f"  {icon} {fs.path}{stat}")
        remaining = len(changelog.file_stats) - len(shown)
        if remaining > 0:
            lines.append(f"  {_DIM}… and {remaining} more files{_RESET}")
        lines.append("")

    lines.append(f"{_DIM}Run 'ocha' to launch the console.{_RESET}")
    return "\n".join(lines)
