"""Build and refresh the SQLite FTS5 index.

TODO(v0.1): walk the wiki clone for ``.md`` files, skip ``.git/``, ``uploads/``
and ``_sidebar.md``, extract titles, populate SQLite FTS5 with the
``unicode61 remove_diacritics 2`` tokenizer, and write metadata (commit, page
count, indexing timestamp). Writes must use a temporary file and an atomic
replace.
"""

from __future__ import annotations

from pathlib import Path

from devecoop_mcp.wiki.models import StatusResponse


def build_index(*, wiki_path: Path, index_path: Path) -> StatusResponse:
    """Build a new index at ``index_path`` from the wiki clone.

    Args:
        wiki_path: Path to the local wiki clone.
        index_path: Destination path for the SQLite index.

    Returns:
        Status metadata for the freshly built index.

    TODO(v0.1): implement index construction.
    """
    raise NotImplementedError("TODO(v0.1): implement index construction")


def read_status(*, wiki_path: Path, index_path: Path) -> StatusResponse:
    """Read clone and index metadata without modifying anything.

    Args:
        wiki_path: Path to the local wiki clone.
        index_path: Path to the SQLite index.

    Returns:
        Current page count, git commit, remote and last indexing timestamp.

    TODO(v0.1): implement status reporting.
    """
    raise NotImplementedError("TODO(v0.1): implement status reporting")
