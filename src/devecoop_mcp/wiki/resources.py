"""MCP resources for the wiki oracle.

TODO(v0.1): register the ``wiki://page/{path}`` resource template. Reading the
resource returns the raw Markdown of the page, URL-decodes the path, enforces
that the resolved file stays inside ``WIKI_PATH``, and rejects non-Markdown
files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def register_resources(mcp: MCPServer) -> None:
    """Register the wiki resources on ``mcp``.

    Args:
        mcp: The Devecoop MCP server instance.

    TODO(v0.1): implement resource registration.
    """
