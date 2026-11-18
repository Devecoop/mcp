"""Command-line interface for the Devecoop MCP server."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from devecoop_mcp import __version__
from devecoop_mcp.core.errors import ConfigurationError
from devecoop_mcp.server import run_server

NOT_IMPLEMENTED_EXIT_CODE = 3


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


def _placeholder(command: str) -> int:
    """Report that ``command`` is not part of the scaffold yet."""
    print(
        f"error: '{command}' is not implemented yet. "
        "This is the v0.1 scaffold; see docs/project-guidelines.md.",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED_EXIT_CODE


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
        return _placeholder("refresh")
    if args.command == "status":
        return _placeholder("status")

    parser.error(f"unknown command: {args.command}")
