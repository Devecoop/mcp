"""Kimai integration feature package.

The feature is registered from :func:`register_kimai`, which is called by the
server factory. The Kimai tools live in :mod:`devecoop_mcp.kimai.tools`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from devecoop_mcp.kimai.client import KimaiClient
from devecoop_mcp.kimai.tools import register_tools

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from devecoop_mcp.config import KimaiConfig


def register_kimai(mcp: MCPServer, config: KimaiConfig) -> None:
    """Register the Kimai tools on the MCP server.

    Args:
        mcp: The Devecoop MCP server instance.
        config: Validated Kimai configuration.
    """
    client = KimaiClient(config)
    register_tools(mcp, client, config)
