"""Git helpers for the local wiki clone."""

from __future__ import annotations

import subprocess
from pathlib import Path


def read_git_output(
    wiki_path: Path,
    *arguments: str,
    timeout: float = 5,
) -> str | None:
    """Run a git command in ``wiki_path`` and return its stdout.

    Args:
        wiki_path: Path to the local git checkout.
        *arguments: Git arguments, for example ``("rev-parse", "--short", "HEAD")``.
        timeout: Seconds to wait before treating the command as failed. The
            default suits local metadata reads; network commands such as
            ``git pull`` should pass a larger value.

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
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip()
