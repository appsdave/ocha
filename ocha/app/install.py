from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


DEFAULT_REPO_URL = "git@github.com:appsdave/ocha.git"
DEFAULT_BRANCH = "main"
DEFAULT_INSTALL_DIRNAME = ".ocha"
DEFAULT_VENV_DIRNAME = ".venv"


class InstallError(RuntimeError):
    pass


@dataclass(slots=True)
class InstallResult:
    action: str
    target: Path
    repo_url: str
    branch: str
    revision: str


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


def ensure_bootstrap(target: Path) -> BootstrapResult:
    target = target.expanduser().resolve()
    venv_dir = target / DEFAULT_VENV_DIRNAME

    if shutil.which("python3") is None:
        raise InstallError("python3 is required but was not found on PATH.")

    if not venv_dir.exists():
        run_command(["python3", "-m", "venv", str(venv_dir)])

    venv_python = venv_dir / "bin" / "python"
    launcher = venv_dir / "bin" / "ocha"
    run_command([str(venv_python), "-m", "pip", "install", "-e", str(target)])

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
    )


def update_repo(target: Path, branch: str = DEFAULT_BRANCH, *, bootstrap: bool = True) -> InstallResult:
    target = target.expanduser().resolve()
    if not (target / ".git").exists():
        raise InstallError(f"Target is not a git checkout: {target}")

    run_git(["fetch", "origin", branch], cwd=target)
    run_git(["checkout", branch], cwd=target)
    run_git(["pull", "--ff-only", "origin", branch], cwd=target)
    if bootstrap:
        ensure_bootstrap(target)
    remote_url = run_git(["remote", "get-url", "origin"], cwd=target).stdout.strip()
    return InstallResult(
        action="updated",
        target=target,
        repo_url=remote_url,
        branch=branch,
        revision=resolve_revision(target),
    )