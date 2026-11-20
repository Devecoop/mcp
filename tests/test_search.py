"""Tests for full-text wiki search."""

from __future__ import annotations

from pathlib import Path

from devecoop_mcp.wiki.index import build_index
from devecoop_mcp.wiki.search import search_wiki

BASE_URL = "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki/-/wikis/"


def _write_page(root: Path, relative_path: str, content: str) -> None:
    page_path = root / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")


def test_search_returns_ranked_results_with_citations(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(
        wiki_path,
        "Reglas/vacaciones.md",
        "# Vacaciones\n\nCada socie tiene 14 días de vacaciones.\n",
    )
    _write_page(
        wiki_path,
        "minutas/2026/Minuta-04-11-2026.md",
        "# Minuta\n\nSe habló de vacaciones y licencias.\n",
    )
    _write_page(wiki_path, "home.md", "# Inicio\n\nTexto sin relación.\n")
    index_path = tmp_path / ".cache" / "wiki_index.sqlite3"
    build_index(wiki_path=wiki_path, index_path=index_path)

    response = search_wiki(
        "vacaciones",
        wiki_path=wiki_path,
        index_path=index_path,
        base_url=BASE_URL,
    )

    assert response.total == 2
    assert len(response.results) == 2
    first = response.results[0]
    assert first.path == "Reglas/vacaciones.md"
    assert first.url is not None
    assert first.url.endswith("/reglas/vacaciones")
    assert "vacaciones" in first.snippet
    assert first.line >= 1
    assert first.score > 0

    limited = search_wiki(
        "vacaciones",
        wiki_path=wiki_path,
        index_path=index_path,
        base_url=BASE_URL,
        limit=1,
    )
    assert len(limited.results) == 1
    assert limited.total == 2

    filtered = search_wiki(
        "vacaciones",
        wiki_path=wiki_path,
        index_path=index_path,
        base_url=BASE_URL,
        path_prefix="minutas",
    )
    assert filtered.total == 1
    assert [result.path for result in filtered.results] == ["minutas/2026/Minuta-04-11-2026.md"]

    phrase = search_wiki(
        '"días de vacaciones"',
        wiki_path=wiki_path,
        index_path=index_path,
        base_url=BASE_URL,
    )
    assert [result.path for result in phrase.results] == ["Reglas/vacaciones.md"]

    stopword_only_query = search_wiki(
        "de la",
        wiki_path=wiki_path,
        index_path=index_path,
        base_url=BASE_URL,
    )
    assert stopword_only_query.total == 0


def test_search_blank_query_returns_empty_results(tmp_path: Path) -> None:
    response = search_wiki(
        " ... ",
        wiki_path=tmp_path,
        index_path=tmp_path / "missing.sqlite3",
    )

    assert response.total == 0
    assert response.results == []
