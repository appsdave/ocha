from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


DEFAULT_REPO_URL = "https://github.com/appsdave/ocha.git"
DEFAULT_BRANCH = "main"
DEFAULT_INSTALL_DIRNAME = ".ocha"
DEFAULT_VENV_DIRNAME = ".venv"
DEFAULT_PROJECT_DIRNAME = "ocha"


class InstallError(RuntimeError):
    pass


@dataclass(slots=True)
class FileChangeStat:
    """Per-file diff stat from a revision range."""
    path: str
    insertions: int
    deletions: int
    status: str  # "added", "modified", "deleted", "renamed"


@dataclass(slots=True)
class UpdateChangelog:
    """Rich changelog between two revisions."""
    branch: str
    previous_revision: str
    revision: str
    commits: list[str]
    file_stats: list[FileChangeStat]
    total_insertions: int
    total_deletions: int
    files_added: int
    files_modified: int
    files_deleted: int


@dataclass(slots=True)
class InstallResult:
    action: str
    target: Path
    repo_url: str
    branch: str
    revision: str
    previous_revision: str | None = None
    changed: bool = True
    change_summary: list[str] = None
    changelog: UpdateChangelog | None = None


@dataclass(slots=True)
class BootstrapResult:
    target: Path
    venv_python: Path
    launcher: Path


def default_install_dir(home_dir: Path | None = None) -> Path:
    root = home_dir or Path.home()
    return root / DEFAULT_INSTALL_DIRNAME


def default_checkout_dir(base_dir: Path | None = None) -> Path:
    return default_install_dir(base_dir)


def resolve_project_dir(target: Path) -> Path:
    target = target.expanduser().resolve()
    direct = target / "pyproject.toml"
    nested = target / DEFAULT_PROJECT_DIRNAME / "pyproject.toml"
    if direct.exists():
        return target
    if nested.exists():
        return nested.parent
    raise InstallError(f"Could not find ocha Python project inside: {target}")


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    if shutil.which("git") is None:
        raise InstallError("git is required but was not found on PATH.")

    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise InstallError(stderr or f"git {' '.join(args)} failed with exit code {result.returncode}.")
    return result


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        command = " ".join(args)
        raise InstallError(stderr or f"{command} failed with exit code {result.returncode}.")
    return result


def resolve_revision(target: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=target).stdout.strip()


def summarize_revision_range(target: Path, previous_revision: str, revision: str, *, limit: int = 8) -> list[str]:
    if previous_revision == revision:
        return []
    result = run_git(
        ["log", "--format=%h %s", f"{previous_revision}..{revision}", f"-n{limit}"],
        cwd=target,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _parse_numstat_line(line: str) -> tuple[int, int, str]:
    """Parse a single line of ``git diff --numstat`` output.

    Returns *(insertions, deletions, path)*.  Binary files report ``-``
    for both counts which we map to ``0``.
    """
    parts = line.split("\t", 2)
    if len(parts) < 3:
        return 0, 0, line.strip()
    ins_s, del_s, path = parts
    ins = int(ins_s) if ins_s != "-" else 0
    dels = int(del_s) if del_s != "-" else 0
    return ins, dels, path.strip()


def _classify_status(status_code: str) -> str:
    """Map a single git status letter to a human-friendly word."""
    mapping = {"A": "added", "D": "deleted", "M": "modified"}
    if status_code.startswith("R"):
        return "renamed"
    return mapping.get(status_code, "modified")


def build_update_changelog(
    target: Path,
    previous_revision: str,
    revision: str,
    branch: str,
    *,
    commit_limit: int = 15,
    file_limit: int = 50,
) -> UpdateChangelog | None:
    """Build a rich changelog between two revisions.

    Returns ``None`` when the revisions are identical (nothing changed).
    """
    if previous_revision == revision:
        return None

    # Commits
    log_result = run_git(
        ["log", "--format=%h %s", f"{previous_revision}..{revision}", f"-n{commit_limit}"],
        cwd=target,
    )
    commits = [l for l in log_result.stdout.splitlines() if l.strip()]

    # Per-file numstat
    numstat_result = run_git(
        ["diff", "--numstat", previous_revision, revision],
        cwd=target,
    )
    # Per-file status letters
    name_status_result = run_git(
        ["diff", "--name-status", previous_revision, revision],
        cwd=target,
    )

    status_map: dict[str, str] = {}
    for line in name_status_result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_map[parts[1].strip()] = _classify_status(parts[0].strip())

    file_stats: list[FileChangeStat] = []
    total_ins = 0
    total_del = 0
    for line in numstat_result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        ins, dels, path = _parse_numstat_line(line)
        total_ins += ins
        total_del += dels
        status = status_map.get(path, "modified")
        file_stats.append(FileChangeStat(path=path, insertions=ins, deletions=dels, status=status))
        if len(file_stats) >= file_limit:
            break

    added = sum(1 for f in file_stats if f.status == "added")
    modified = sum(1 for f in file_stats if f.status == "modified")
    deleted = sum(1 for f in file_stats if f.status == "deleted")

    return UpdateChangelog(
        branch=branch,
        previous_revision=previous_revision,
        revision=revision,
        commits=commits,
        file_stats=file_stats,
        total_insertions=total_ins,
        total_deletions=total_del,
        files_added=added,
        files_modified=modified,
        files_deleted=deleted,
    )


def ensure_bootstrap(target: Path) -> BootstrapResult:
    target = target.expanduser().resolve()
    project_dir = resolve_project_dir(target)
    venv_dir = target / DEFAULT_VENV_DIRNAME

    if shutil.which("python3") is None:
        raise InstallError("python3 is required but was not found on PATH.")

    if not venv_dir.exists():
        run_command(["python3", "-m", "venv", str(venv_dir)])

    venv_python = venv_dir / "bin" / "python"
    launcher = venv_dir / "bin" / "ocha"
    run_command([str(venv_python), "-m", "pip", "install", "-e", str(project_dir)])

    return BootstrapResult(target=target, venv_python=venv_python, launcher=launcher)


def relaunch_from_bootstrap(bootstrap: BootstrapResult, argv: list[str] | None = None) -> NoReturn:
    args = [str(bootstrap.launcher), *(argv or [])]
    os.execv(str(bootstrap.launcher), args)


def clone_repo(
    target: Path,
    repo_url: str = DEFAULT_REPO_URL,
    branch: str = DEFAULT_BRANCH,
    *,
    force: bool = False,
    bootstrap: bool = True,
) -> InstallResult:
    target = target.expanduser().resolve()
    if target.exists():
        if any(target.iterdir()) and not force:
            raise InstallError(f"Target already exists and is not empty: {target}")
        if force:
            shutil.rmtree(target)
        else:
            target.rmdir()

    target.parent.mkdir(parents=True, exist_ok=True)
    run_git(["clone", "--branch", branch, repo_url, str(target)])
    if bootstrap:
        ensure_bootstrap(target)
    return InstallResult(
        action="downloaded",
        target=target,
        repo_url=repo_url,
        branch=branch,
        revision=resolve_revision(target),
        change_summary=[],
    )


# Files that should survive a git reset --hard (user secrets, local config)
_PRESERVED_FILES = [".env"]


def update_repo(target: Path, branch: str = DEFAULT_BRANCH, *, bootstrap: bool = True) -> InstallResult:
    target = target.expanduser().resolve()
    if not (target / ".git").exists():
        raise InstallError(f"Target is not a git checkout: {target}")

    # Back up user files that must survive the hard reset
    saved: dict[str, bytes] = {}
    for name in _PRESERVED_FILES:
        p = target / name
        if p.is_file():
            saved[name] = p.read_bytes()

    previous_revision = resolve_revision(target)
    run_git(["fetch", "origin", branch], cwd=target)
    run_git(["checkout", branch], cwd=target)
    run_git(["reset", "--hard", "FETCH_HEAD"], cwd=target)

    # Restore preserved files
    for name, data in saved.items():
        p = target / name
        p.write_bytes(data)
        p.chmod(0o600)
    if bootstrap:
        ensure_bootstrap(target)
    remote_url = run_git(["remote", "get-url", "origin"], cwd=target).stdout.strip()
    revision = resolve_revision(target)
    change_summary = summarize_revision_range(target, previous_revision, revision)
    changelog = build_update_changelog(target, previous_revision, revision, branch)
    return InstallResult(
        action="updated" if revision != previous_revision else "already-latest",
        target=target,
        repo_url=remote_url,
        branch=branch,
        revision=revision,
        previous_revision=previous_revision,
        changed=revision != previous_revision,
        change_summary=change_summary,
        changelog=changelog,
    )