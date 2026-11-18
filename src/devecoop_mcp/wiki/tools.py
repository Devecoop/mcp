"""MCP tools for the wiki oracle.

TODO(v0.1): register the four read-only tools on the server:

- ``wiki_search``: FTS5 search with snippets, paths and GitLab URLs.
- ``wiki_read_page``: full Markdown content for a page.
- ``wiki_list_pages``: page listing filtered by path prefix.
- ``wiki_status``: clone and index metadata.

All tools return structured JSON and carry read-only tool annotations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def register_tools(mcp: MCPServer) -> None:
    """Register the wiki tools on ``mcp``.

    Args:
        mcp: The Devecoop MCP server instance.

    TODO(v0.1): implement tool registration.
    """
