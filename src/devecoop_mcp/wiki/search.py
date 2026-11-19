"""Full-text search over the local wiki index."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from devecoop_mcp.wiki.index import open_index_read_only
from devecoop_mcp.wiki.models import SearchResponse, SearchResult
from devecoop_mcp.wiki.urls import page_url

DEFAULT_RESULT_LIMIT = 8
MAX_RESULT_LIMIT = 20

SPANISH_STOPWORDS = {
    "a",
    "al",
    "algo",
    "algun",
    "alguna",
    "algunas",
    "alguno",
    "algunos",
    "aunque",
    "como",
    "con",
    "cual",
    "cuales",
    "cuando",
    "cuanta",
    "cuantas",
    "cuanto",
    "cuantos",
    "de",
    "del",
    "desde",
    "donde",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estan",
    "estas",
    "este",
    "esto",
    "estos",
    "fue",
    "ha",
    "han",
    "hasta",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "mas",
    "me",
    "mi",
    "mis",
    "mucho",
    "mucha",
    "muchas",
    "muchos",
    "muy",
    "no",
    "nos",
    "o",
    "para",
    "pero",
    "por",
    "porque",
    "que",
    "quien",
    "quienes",
    "salio",
    "se",
    "ser",
    "si",
    "sin",
    "sobre",
    "son",
    "su",
    "sus",
    "tambien",
    "te",
    "tenemos",
    "tiene",
    "tienen",
    "tu",
    "tus",
    "un",
    "una",
    "unas",
    "uno",
    "unos",
    "y",
    "ya",
}


def _normalize_term(value: str) -> str:
    """Lowercase and remove accents so stopword matching is accent-insensitive."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _build_fts_query(query: str) -> str:
    """Turn user input into a safe FTS5 query of quoted phrases joined by OR."""
    terms: list[str] = []
    for quoted_phrase, bare_term in re.findall(r'"([^"]+)"|(\S+)', query):
        value = re.sub(r"\W+", " ", quoted_phrase or bare_term).strip()
        if value and _normalize_term(value) not in SPANISH_STOPWORDS:
            terms.append(f'"{value}"')
    return " OR ".join(terms)


def _snippet_line(body: str, snippet: str) -> int:
    """Return the 1-based line where the snippet fragment starts."""
    fragment = snippet.strip().strip("…").strip()
    position = body.find(fragment) if fragment else -1
    if position == -1:
        return 1
    return body.count("\n", 0, position) + 1


def search_wiki(
    query: str,
    *,
    wiki_path: Path,
    index_path: Path,
    base_url: str | None = None,
    limit: int = DEFAULT_RESULT_LIMIT,
    path_prefix: str | None = None,
) -> SearchResponse:
    """Search the SQLite FTS5 index for wiki pages matching ``query``.

    Args:
        query: Natural-language or keyword query from the model.
        wiki_path: Path to the local wiki clone.
        index_path: Path to the SQLite index built by ``devecoop-mcp refresh``.
        base_url: Optional GitLab base URL override for citations.
        limit: Maximum number of pages to return.
        path_prefix: Optional page path prefix, for example ``minutas/2026``.

    Returns:
        Ranked search results with snippets, paths, lines and citation URLs.
    """
    fts_query = _build_fts_query(query)
    if not fts_query:
        return SearchResponse(query=query, results=[], total=0)

    limit = max(1, min(limit, MAX_RESULT_LIMIT))
    match_clause = "pages MATCH ?"
    match_parameters: list[str | int] = [fts_query]
    if path_prefix is not None:
        match_clause += " AND path LIKE ?"
        match_parameters.append(f"{path_prefix}%")

    connection = open_index_read_only(index_path)
    try:
        total = connection.execute(
            f"SELECT COUNT(*) FROM pages WHERE {match_clause}", match_parameters
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT path, title, body,
                   snippet(pages, 2, '', '', '…', 48) AS snippet,
                   -bm25(pages, 0.0, 2.0, 1.0) AS score
            FROM pages
            WHERE {match_clause}
            ORDER BY score DESC
            LIMIT ?
            """,
            [*match_parameters, limit],
        ).fetchall()
    finally:
        connection.close()

    results = [
        SearchResult(
            path=path,
            title=title,
            url=page_url(wiki_path=wiki_path, page_path=path, base_url=base_url),
            snippet=snippet,
            line=_snippet_line(body, snippet),
            score=float(score),
        )
        for path, title, body, snippet, score in rows
    ]
    return SearchResponse(query=query, results=results, total=int(total))
