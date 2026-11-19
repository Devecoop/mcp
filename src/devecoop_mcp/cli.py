"""Command-line interface for the Devecoop MCP server."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from devecoop_mcp import __version__
from devecoop_mcp.config import Settings
from devecoop_mcp.core.errors import ConfigurationError
from devecoop_mcp.core.git import read_git_output
from devecoop_mcp.server import run_server
from devecoop_mcp.wiki.index import build_index, read_status


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the ``devecoop-mcp`` command."""
    parser = argparse.ArgumentParser(
        prog="devecoop-mcp",
        description="Local MCP server (stdio) for the Devecoop GitLab wiki.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.add_parser("serve", help="Run the MCP server over stdio (default).")
    subparsers.add_parser("refresh", help="Update the wiki clone and rebuild the index.")
    subparsers.add_parser("status", help="Show wiki clone and index status.")
    return parser


def _serve() -> int:
    """Run the stdio server and translate configuration errors into exit codes."""
    try:
        run_server()
    except (ConfigurationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _resolve_wiki_paths() -> tuple[Path, Path] | None:
    """Return the wiki and index paths, or report a configuration error."""
    try:
        settings = Settings()
        return settings.require_wiki_path(), settings.wiki_index_path
    except (ConfigurationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _refresh() -> int:
    """Pull the wiki clone and rebuild the index."""
    paths = _resolve_wiki_paths()
    if paths is None:
        return 2
    wiki_path, index_path = paths

    pull_output = read_git_output(wiki_path, "pull", "--ff-only", timeout=60)
    if pull_output is None:
        print(f"error: git pull --ff-only failed in {wiki_path}", file=sys.stderr)
        return 1
    if pull_output:
        print(pull_output)

    try:
        status = build_index(wiki_path=wiki_path, index_path=index_path)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Indexed {status.page_count} pages into {status.index_path}")
    if status.git_commit:
        print(f"Wiki commit: {status.git_commit}")
    if status.last_indexed_at:
        print(f"Last indexed: {status.last_indexed_at}")
    return 0


def _status() -> int:
    """Print the current wiki clone and index status."""
    paths = _resolve_wiki_paths()
    if paths is None:
        return 2
    wiki_path, index_path = paths

    try:
        status = read_status(wiki_path=wiki_path, index_path=index_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wiki path: {status.wiki_path}")
    print(f"Index path: {status.index_path}")
    print(f"Pages: {status.page_count}")
    print(f"Last indexed: {status.last_indexed_at or 'never'}")
    print(f"Git commit: {status.git_commit or 'unknown'}")
    print(f"Git remote: {status.git_remote or 'unknown'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "serve"):
        return _serve()
    if args.command == "refresh":
        return _refresh()
    if args.command == "status":
        return _status()

    parser.error(f"unknown command: {args.command}")
