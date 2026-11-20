"""Wiki oracle feature package.

The feature is registered from :func:`register_wiki`, which is called by the
server factory. The wiki tools live in :mod:`devecoop_mcp.wiki.tools`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from devecoop_mcp.wiki.tools import register_tools

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from devecoop_mcp.config import Settings


def register_wiki(mcp: MCPServer, settings: Settings) -> None:
    """Register the wiki tools on the MCP server.

    Args:
        mcp: The Devecoop MCP server instance.
        settings: Runtime configuration with the wiki path and index settings.
    """
    register_tools(mcp, settings)
