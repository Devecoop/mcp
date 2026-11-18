"""MCP prompts for the wiki oracle.

TODO(v0.1): register the ``ask_wiki`` prompt. It receives a topic and returns a
user message instructing the model to search with ``wiki_search``, read the
relevant pages with ``wiki_read_page``, answer only from wiki evidence, cite
the URL of every source and say explicitly when no evidence exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def register_prompts(mcp: MCPServer) -> None:
    """Register the wiki prompts on ``mcp``.

    Args:
        mcp: The Devecoop MCP server instance.

    TODO(v0.1): implement prompt registration.
    """
