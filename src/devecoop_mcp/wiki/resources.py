"""MCP resources for the wiki oracle.

The ``wiki://page/{path}`` template returns the raw Markdown of a page. The path
is URL-decoded and resolved through the same path-safety rules used by the
``wiki_read_page`` tool, so traversal, absolute paths, symlink escapes and
non-Markdown files are rejected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

from devecoop_mcp.wiki.index import resolve_wiki_page_path

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from devecoop_mcp.config import Settings


def register_resources(mcp: MCPServer, settings: Settings) -> None:
    """Register the wiki resources on ``mcp``.

    Args:
        mcp: The Devecoop MCP server instance.
        settings: Runtime configuration with the wiki path.
    """

    @mcp.resource("wiki://page/{path}", mime_type="text/markdown")
    def wiki_page(path: str) -> str:
        """Read a wiki page as Markdown. The path is URL-encoded relative to the wiki root."""
        wiki_path = settings.require_wiki_path()
        decoded_path = unquote(path)
        page_file = resolve_wiki_page_path(wiki_path, decoded_path)
        return page_file.read_text(encoding="utf-8")
