from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .install import DEFAULT_BRANCH, DEFAULT_REPO_URL, InstallError, clone_repo, default_checkout_dir, update_repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocha", description="Python/Textual rebuild of the ocha operator console")
    parser.add_argument(
        "--version",
        action="version",
        version="ocha 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command")

    download = subparsers.add_parser("download", help="Clone the ocha repository to a local checkout")
    download.add_argument("target", nargs="?", default=None, help="Destination directory for the checkout")
    download.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository to clone")
    download.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to clone")
    download.add_argument("--force", action="store_true", help="Replace an existing target directory")

    update = subparsers.add_parser("update", help="Fast-forward an existing ocha checkout from origin")
    update.add_argument("target", nargs="?", default=None, help="Checkout directory to update")
    update.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to update")

    subparsers.add_parser("tui", help="Launch the Textual TUI")
    return parser


def resolve_target(raw_target: str | None) -> Path:
    if raw_target:
        return Path(raw_target).expanduser()
    return default_checkout_dir()


def launch_tui() -> int:
    from .app import OchaApp

    OchaApp().run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command or "tui"
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
            print(f"Updated {result.target} from {result.repo_url} on {result.branch} @ {result.revision}")
            return 0
        if command == "tui":
            return launch_tui()
        parser.error(f"Unknown command: {command}")
    except InstallError as error:
        print(f"ocha: {error}", file=sys.stderr)
        return 1
    return 0