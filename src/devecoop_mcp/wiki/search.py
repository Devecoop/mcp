"""Full-text search over the local wiki index.

TODO(v0.1): sanitize FTS5 queries, run BM25 ranking with title/heading boosts,
build ~400 character snippets around the best match, respect ``path_prefix``
and cap results at 20.
"""

from __future__ import annotations

from pathlib import Path

from devecoop_mcp.wiki.models import SearchResponse

DEFAULT_RESULT_LIMIT = 8
MAX_RESULT_LIMIT = 20


def search_wiki(
    query: str,
    *,
    index_path: Path,
    limit: int = DEFAULT_RESULT_LIMIT,
    path_prefix: str | None = None,
) -> SearchResponse:
    """Search the SQLite FTS5 index for wiki pages matching ``query``.

    Args:
        query: Natural-language or keyword query from the model.
        index_path: Path to the SQLite index built by ``devecoop-mcp refresh``.
        limit: Maximum number of pages to return.
        path_prefix: Optional page path prefix, for example ``minutas/2026``.

    Returns:
        Ranked search results with snippets, paths, lines and citation URLs.

    TODO(v0.1): implement the search.
    """
    raise NotImplementedError("TODO(v0.1): implement FTS5 search")
