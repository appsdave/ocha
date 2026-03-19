from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPO_URL = "git@github.com:appsdave/ocha.git"
DEFAULT_BRANCH = "main"


class InstallError(RuntimeError):
    pass


@dataclass(slots=True)
class InstallResult:
    action: str
    target: Path
    repo_url: str
    branch: str
    revision: str


def default_checkout_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or Path.home() / ".local" / "share" / "ocha"
    return root / "checkout"


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


def resolve_revision(target: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=target).stdout.strip()


def clone_repo(
    target: Path,
    repo_url: str = DEFAULT_REPO_URL,
    branch: str = DEFAULT_BRANCH,
    *,
    force: bool = False,
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
    return InstallResult(
        action="downloaded",
        target=target,
        repo_url=repo_url,
        branch=branch,
        revision=resolve_revision(target),
    )


def update_repo(target: Path, branch: str = DEFAULT_BRANCH) -> InstallResult:
    target = target.expanduser().resolve()
    if not (target / ".git").exists():
        raise InstallError(f"Target is not a git checkout: {target}")

    run_git(["fetch", "origin", branch], cwd=target)
    run_git(["checkout", branch], cwd=target)
    run_git(["pull", "--ff-only", "origin", branch], cwd=target)
    remote_url = run_git(["remote", "get-url", "origin"], cwd=target).stdout.strip()
    return InstallResult(
        action="updated",
        target=target,
        repo_url=remote_url,
        branch=branch,
        revision=resolve_revision(target),
    )