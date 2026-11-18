"""Derivation of GitLab wiki URLs for citation links.

TODO(v0.1): read ``origin`` from the wiki clone, convert
``git@gitlab.apps.devecoop.coop.ar:devecoop/wiki.wiki.git`` into
``https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/<path>``,
URL-encode the page path and honour the ``WIKI_BASE_URL`` override.
"""

from __future__ import annotations

from pathlib import Path


def derive_base_url(wiki_path: Path) -> str | None:
    """Return the GitLab base URL derived from the wiki clone's remote.

    Args:
        wiki_path: Path to the local wiki clone.

    Returns:
        The GitLab wiki base URL, or ``None`` when the remote cannot be parsed.

    TODO(v0.1): implement remote parsing.
    """
    raise NotImplementedError("TODO(v0.1): implement GitLab remote parsing")


def page_url(
    *,
    wiki_path: Path,
    page_path: str,
    base_url: str | None = None,
) -> str | None:
    """Build the citation URL for a page inside the wiki.

    Args:
        wiki_path: Path to the local wiki clone.
        page_path: Page path relative to the wiki root, for example ``Reglas/vacaciones.md``.
        base_url: Optional explicit base URL that overrides the git remote.

    Returns:
        The GitLab URL for the page, or ``None`` when it cannot be derived.

    TODO(v0.1): implement URL encoding and path-to-slug conversion.
    """
    raise NotImplementedError("TODO(v0.1): implement GitLab page URL derivation")
