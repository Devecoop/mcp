"""Tests for the SQLite FTS5 wiki index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from devecoop_mcp.wiki.index import build_index, read_status


def _write_page(root: Path, relative_path: str, content: str) -> None:
    page_path = root / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")


def test_build_index_indexes_pages_and_skips_excluded_files(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(wiki_path, "home.md", "# Inicio\n")
    _write_page(wiki_path, "Reglas/vacaciones.md", "# Vacaciones\n\nCada socie tiene días.\n")
    _write_page(wiki_path, "minutas/2026/Minuta-04-11-2026.md", "Sin encabezado.\n")
    _write_page(wiki_path, "_sidebar.md", "# Navegación\n")
    _write_page(wiki_path, "uploads/nota.md", "# Nota\n")

    index_path = tmp_path / ".cache" / "wiki_index.sqlite3"
    status = build_index(wiki_path=wiki_path, index_path=index_path)

    assert status.page_count == 3
    assert status.wiki_path == str(wiki_path)
    assert status.index_path == str(index_path)
    assert status.last_indexed_at is not None
    assert status.git_commit is None
    assert status.git_remote is None

    connection = sqlite3.connect(index_path)
    try:
        rows = connection.execute("SELECT path, title FROM pages ORDER BY path").fetchall()
        matches = connection.execute(
            "SELECT path FROM pages WHERE pages MATCH 'vacaciones'"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        ("Reglas/vacaciones.md", "Vacaciones"),
        ("home.md", "Inicio"),
        ("minutas/2026/Minuta-04-11-2026.md", "Minuta 04 11 2026"),
    ]
    assert [row[0] for row in matches] == ["Reglas/vacaciones.md"]


def test_read_status_requires_existing_index(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="refresh"):
        read_status(wiki_path=tmp_path, index_path=tmp_path / "missing.sqlite3")
