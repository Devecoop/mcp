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


def register_wiki(mcp: MCPServer) -> None:
    """Register all wiki primitives on the MCP server.

    Args:
        mcp: The Devecoop MCP server instance.
    """
    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
