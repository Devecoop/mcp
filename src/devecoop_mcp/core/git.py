"""Read-only helpers for git metadata."""

from __future__ import annotations

import subprocess
from pathlib import Path


def read_git_output(wiki_path: Path, *arguments: str) -> str | None:
    """Run a read-only git command in ``wiki_path`` and return its stdout.

    Args:
        wiki_path: Path to the local git checkout.
        *arguments: Git arguments, for example ``("rev-parse", "--short", "HEAD")``.

    Returns:
        The stripped stdout on success, or ``None`` when git is unavailable or
        the command fails.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(wiki_path), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip()
