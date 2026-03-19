from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .orchestrator import build_launch_specs
from .install import (
    DEFAULT_BRANCH,
    DEFAULT_REPO_URL,
    InstallError,
    clone_repo,
    default_install_dir,
    ensure_bootstrap,
    relaunch_from_bootstrap,
    update_repo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocha", description="Python/Textual rebuild of the ocha operator console")
    parser.add_argument(
        "--version",
        action="version",
        version="ocha 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command")

    download = subparsers.add_parser("download", help="Clone the ocha repository to ~/.ocha and install its runtime")
    download.add_argument("target", nargs="?", default=None, help="Destination directory for the managed ocha install")
    download.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository to clone")
    download.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to clone")
    download.add_argument("--force", action="store_true", help="Replace an existing target directory")

    update = subparsers.add_parser("update", help="Update an existing ~/.ocha install from origin and refresh its runtime")
    update.add_argument("target", nargs="?", default=None, help="Managed ocha install directory to update")
    update.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to update")

    launch = subparsers.add_parser("launch", help="Prepare role-based headless Junie launches for a new ocha task")
    launch.add_argument("task", help="Top-level task to hand to the ocha orchestrator")
    launch.add_argument("--project", default=".", help="Project path passed to Junie headless sessions")
    return parser


def resolve_target(raw_target: str | None) -> Path:
    if raw_target:
        return Path(raw_target).expanduser()
    return default_install_dir()


def launch_tui() -> int:
    try:
        from .app import OchaApp
    except ModuleNotFoundError as error:
        if error.name != "textual":
            raise

        target = default_install_dir()
        if not target.exists() or not (target / "pyproject.toml").exists():
            clone_repo(target)
        bootstrap = ensure_bootstrap(target)
        relaunch_from_bootstrap(bootstrap)
        return 0

    OchaApp().run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command
    try:
        if command == "download":
            result = clone_repo(
                resolve_target(args.target),
                repo_url=args.repo_url,
                branch=args.branch,
                force=args.force,
            )
            print(f"Downloaded {result.repo_url} to {result.target} on {result.branch} @ {result.revision}")
            return 0
        if command == "update":
            result = update_repo(resolve_target(args.target), branch=args.branch)
            if result.changed:
                print(f"Updated {result.target} from {result.repo_url} on {result.branch} @ {result.revision}")
                if result.previous_revision:
                    print(f"Previous revision: {result.previous_revision}")
                if result.change_summary:
                    print("Changes:")
                    for line in result.change_summary:
                        print(f"- {line}")
            else:
                print("Already up to date")
            return 0
        if command == "launch":
            specs = build_launch_specs(args.task, project_path=Path(args.project).expanduser())
            for spec in specs:
                print(f"[{spec.role}] {spec.session_id} -> {spec.worktree_path}")
                print(f"  prompt: {spec.prompt_path}")
                print(f"  command: {' '.join(spec.command[:-1])} <prompt>")
            return 0
        if command is None:
            return launch_tui()
        parser.error(f"Unknown command: {command}")
    except InstallError as error:
        print(f"ocha: {error}", file=sys.stderr)
        return 1
    return 0