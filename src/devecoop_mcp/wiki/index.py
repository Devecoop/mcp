"""Build and read the SQLite FTS5 index for the local wiki clone.

The index stores one row per ``.md`` page and metadata about the clone. Builds
write to a temporary file and replace the previous index atomically, so readers
never observe a partially written index.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from devecoop_mcp.core.git import read_git_output
from devecoop_mcp.wiki.models import StatusResponse

SCHEMA_VERSION = "1"
EXCLUDED_DIRECTORIES = {".git", "uploads"}
EXCLUDED_FILES = {"_sidebar.md"}

SCHEMA = """
CREATE VIRTUAL TABLE pages USING fts5(
    path UNINDEXED,
    title,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class WikiPage:
    """A Markdown page ready to be indexed."""

    path: str
    title: str
    body: str


def extract_title(content: str, page_stem: str) -> str:
    """Return the first H1 title, falling back to the humanized file stem."""
    fallback = page_stem.replace("-", " ")
    for line in content.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip() or fallback
    return fallback


def resolve_wiki_page_path(wiki_path: Path, page_path: str) -> Path:
    """Resolve a wiki-relative Markdown path, rejecting escapes and non-Markdown files.

    Args:
        wiki_path: Path to the local wiki clone.
        page_path: Page path relative to the wiki root, as sent by the model.

    Returns:
        The resolved path to an existing Markdown file inside the wiki clone.

    Raises:
        ValueError: If the path escapes the wiki root or is not a Markdown file.
        FileNotFoundError: If the resolved path is not an existing file.
    """
    root = wiki_path.resolve()
    candidate = (root / page_path).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() != ".md":
        raise ValueError(f"Invalid wiki page path: {page_path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Wiki page not found: {page_path}")
    return candidate


def _read_wiki_pages(wiki_path: Path) -> list[WikiPage]:
    """Read all indexable Markdown pages from the wiki clone."""
    pages: list[WikiPage] = []
    for page_path in sorted(wiki_path.rglob("*.md")):
        relative_path = page_path.relative_to(wiki_path)
        if relative_path.name in EXCLUDED_FILES:
            continue
        if EXCLUDED_DIRECTORIES.intersection(relative_path.parts):
            continue

        content = page_path.read_text(encoding="utf-8")
        pages.append(
            WikiPage(
                path=relative_path.as_posix(),
                title=extract_title(content, page_path.stem),
                body=content,
            )
        )
    return pages


def _write_index(temp_path: Path, pages: list[WikiPage], metadata: dict[str, str]) -> None:
    """Create the SQLite schema and populate pages and metadata."""
    connection = sqlite3.connect(temp_path)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO pages (path, title, body) VALUES (?, ?, ?)",
            [(page.path, page.title, page.body) for page in pages],
        )
        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            metadata.items(),
        )
        connection.commit()
    finally:
        connection.close()


def open_index_read_only(index_path: Path) -> sqlite3.Connection:
    """Open an existing index in read-only mode."""
    if not index_path.is_file():
        raise FileNotFoundError(
            f"Index not found at {index_path}. Run 'devecoop-mcp refresh' first."
        )
    return sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)


def build_index(*, wiki_path: Path, index_path: Path) -> StatusResponse:
    """Build a new index at ``index_path`` from the wiki clone.

    Args:
        wiki_path: Path to the local wiki clone.
        index_path: Destination path for the SQLite index.

    Returns:
        Status metadata for the freshly built index.
    """
    if not wiki_path.is_dir():
        raise FileNotFoundError(f"Wiki path not found: {wiki_path}")

    pages = _read_wiki_pages(wiki_path)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "page_count": str(len(pages)),
        "last_indexed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": read_git_output(wiki_path, "rev-parse", "--short", "HEAD") or "",
        "git_remote": read_git_output(wiki_path, "remote", "get-url", "origin") or "",
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = index_path.with_name(f"{index_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        _write_index(temp_path, pages, metadata)
        os.replace(temp_path, index_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return read_status(wiki_path=wiki_path, index_path=index_path)


def read_status(*, wiki_path: Path, index_path: Path) -> StatusResponse:
    """Read clone and index metadata without modifying anything.

    Args:
        wiki_path: Path to the local wiki clone.
        index_path: Path to the SQLite index.

    Returns:
        Current page count, git commit, remote and last indexing timestamp.
    """
    connection = open_index_read_only(index_path)
    try:
        metadata: dict[str, str] = dict(connection.execute("SELECT key, value FROM metadata"))
    finally:
        connection.close()

    return StatusResponse(
        wiki_path=str(wiki_path),
        index_path=str(index_path),
        page_count=int(metadata["page_count"]),
        last_indexed_at=metadata.get("last_indexed_at"),
        git_commit=metadata.get("git_commit") or None,
        git_remote=metadata.get("git_remote") or None,
    )
