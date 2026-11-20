"""Derivation of GitLab wiki URLs for citation links.

The Devecoop wiki is cloned from GitLab over SSH. GitLab serves the wiki at
``https://<host>/<group>/<project>/-/wikis/`` and resolves page paths in
lowercase.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from devecoop_mcp.core.git import read_git_output

WIKI_PATH_SUFFIX = "/-/wikis"


def parse_remote_url(remote: str) -> str | None:
    """Convert the Devecoop SSH wiki remote into its GitLab web base URL.

    Args:
        remote: Git remote as returned by ``git remote get-url origin``.

    Returns:
        The wiki base URL, or ``None`` when the remote does not have the
        expected ``git@<host>:<project>.wiki.git`` shape.
    """
    remote = remote.strip()
    if not remote.startswith("git@"):
        return None

    host_and_project = remote.removeprefix("git@")
    host, separator, project_path = host_and_project.partition(":")
    if not separator or not host or not project_path:
        return None

    project_path = project_path.removesuffix(".git").removesuffix(".wiki")
    if not project_path:
        return None

    return f"https://{host}/{project_path}{WIKI_PATH_SUFFIX}/"


def derive_base_url(wiki_path: Path) -> str | None:
    """Return the wiki base URL derived from the clone's ``origin`` remote.

    Args:
        wiki_path: Path to the local wiki clone.

    Returns:
        The wiki base URL, or ``None`` when git fails or the remote is not
        recognized.
    """
    remote = read_git_output(wiki_path, "remote", "get-url", "origin")
    if remote is None:
        return None
    return parse_remote_url(remote)


def page_path_to_slug(page_path: str) -> str:
    """Convert a relative Markdown page path into a GitLab wiki slug.

    Args:
        page_path: Page path relative to the wiki root.

    Returns:
        The lowercase, URL-encoded page slug.
    """
    slug = page_path.removesuffix(".md").lower().replace(" ", "-")
    return quote(slug, safe="/")


def page_url(
    *,
    wiki_path: Path,
    page_path: str,
    base_url: str | None = None,
) -> str | None:
    """Build the GitLab citation URL for a wiki page.

    Args:
        wiki_path: Path to the local wiki clone.
        page_path: Page path relative to the wiki root.
        base_url: Optional base URL override from configuration.

    Returns:
        The page URL, or ``None`` when no base URL is available.
    """
    base = base_url if base_url is not None else derive_base_url(wiki_path)
    if not base:
        return None

    base = base.rstrip("/")
    if not base.endswith(WIKI_PATH_SUFFIX):
        base = f"{base}{WIKI_PATH_SUFFIX}"
    return f"{base}/{page_path_to_slug(page_path)}"
