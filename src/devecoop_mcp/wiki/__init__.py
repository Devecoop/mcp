"""Wiki oracle feature package.

The feature is registered from :func:`register_wiki`, which is called by the
server factory. Each MCP primitive lives in its own module so tools, resources
and prompts can grow independently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from devecoop_mcp.wiki.prompts import register_prompts
from devecoop_mcp.wiki.resources import register_resources
from devecoop_mcp.wiki.tools import register_tools

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from devecoop_mcp.config import Settings


def register_wiki(mcp: MCPServer, settings: Settings) -> None:
    """Register all wiki primitives on the MCP server.

    Args:
        mcp: The Devecoop MCP server instance.
        settings: Runtime configuration with the wiki path and index settings.
    """
    register_tools(mcp, settings)
    register_resources(mcp, settings)
    register_prompts(mcp)
