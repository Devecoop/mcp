"""Tests for the SQLite FTS5 wiki index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from devecoop_mcp.wiki.index import build_index, read_status, resolve_wiki_page_path


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


def test_resolve_wiki_page_path_accepts_markdown_inside_wiki(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    _write_page(wiki_path, "Reglas/vacaciones.md", "# Vacaciones\n")

    resolved = resolve_wiki_page_path(wiki_path, "Reglas/vacaciones.md")

    assert resolved.is_file()
    assert resolved == wiki_path.resolve() / "Reglas" / "vacaciones.md"


@pytest.mark.parametrize(
    "page_path",
    ["../secret.md", "/etc/passwd", "Reglas/vacaciones.txt"],
)
def test_resolve_wiki_page_path_rejects_invalid_paths(tmp_path: Path, page_path: str) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(tmp_path, "secret.md", "# Secret\n")
    _write_page(wiki_path, "Reglas/vacaciones.txt", "Texto plano.\n")

    with pytest.raises(ValueError, match="Invalid wiki page path"):
        resolve_wiki_page_path(wiki_path, page_path)


def test_resolve_wiki_page_path_rejects_missing_page(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()

    with pytest.raises(FileNotFoundError, match="Wiki page not found"):
        resolve_wiki_page_path(wiki_path, "Reglas/missing.md")


def test_resolve_wiki_page_path_rejects_symlink_escape(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    outside_page = tmp_path / "outside.md"
    outside_page.write_text("# Outside\n", encoding="utf-8")
    (wiki_path / "escape.md").symlink_to(outside_page)

    with pytest.raises(ValueError, match="Invalid wiki page path"):
        resolve_wiki_page_path(wiki_path, "escape.md")
