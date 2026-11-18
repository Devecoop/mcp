"""Pydantic models for the planned wiki tool contracts.

These models mirror the JSON contracts documented in ``docs/project-guidelines.md``.
Search and indexing behaviour is implemented in later tasks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single wiki page match with citation metadata."""

    path: str = Field(
        description="Page path relative to the wiki root, for example 'Reglas/vacaciones.md'.",
    )
    title: str = Field(description="Page title taken from the first H1 or the file name.")
    url: str | None = Field(
        default=None,
        description="GitLab URL for citations, or null when it cannot be derived.",
    )
    snippet: str = Field(description="Exact wiki text that supports the answer.")
    line: int = Field(ge=1, description="Approximate line where the snippet starts.")
    score: float = Field(description="BM25 relevance score.")


class SearchResponse(BaseModel):
    """Result of a ``wiki_search`` call."""

    query: str
    results: list[SearchResult]
    total: int = Field(ge=0, description="Number of matching pages.")


class PageResponse(BaseModel):
    """Result of a ``wiki_read_page`` call."""

    path: str
    title: str
    url: str | None = None
    content: str = Field(description="Full Markdown content of the page.")
    line_count: int = Field(ge=0)


class PageSummary(BaseModel):
    """A page entry returned by ``wiki_list_pages``."""

    path: str
    title: str
    url: str | None = None


class StatusResponse(BaseModel):
    """Result of a ``wiki_status`` call."""

    wiki_path: str
    index_path: str
    page_count: int = Field(ge=0)
    last_indexed_at: str | None = None
    git_commit: str | None = None
    git_remote: str | None = None
