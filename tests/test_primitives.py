"""Tests for the wiki MCP resource and prompt primitives."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp.types import TextContent

from devecoop_mcp.config import Settings
from devecoop_mcp.server import create_server


def _write_page(root: Path, relative_path: str, content: str) -> None:
    page_path = root / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")


async def test_wiki_page_resource_returns_markdown(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(wiki_path, "Reglas/vacaciones.md", "# Vacaciones\n\nCada socie tiene días.\n")
    _write_page(tmp_path, "secret.md", "# Secret\n")
    server = create_server(
        Settings(wiki_path=wiki_path, wiki_index_path=wiki_path / "index.sqlite3")
    )

    templates = await server.list_resource_templates()
    assert any(
        template.uri_template == "wiki://page/{path}" and template.mime_type == "text/markdown"
        for template in templates
    )

    contents = await server.read_resource("wiki://page/Reglas%2Fvacaciones.md")

    assert "# Vacaciones" in "".join(str(item.content) for item in contents)

    with pytest.raises(ResourceNotFoundError):
        await server.read_resource("wiki://page/..%2Fsecret.md")


async def test_ask_wiki_prompt_is_registered(tmp_path: Path) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    server = create_server(
        Settings(wiki_path=wiki_path, wiki_index_path=wiki_path / "index.sqlite3")
    )

    prompts = await server.list_prompts()
    assert "ask_wiki" in [prompt.name for prompt in prompts]

    result = await server.get_prompt("ask_wiki", {"topic": "vacaciones"})
    prompt_text = "".join(
        message.content.text
        for message in result.messages
        if isinstance(message.content, TextContent)
    )

    assert "wiki_search" in prompt_text
    assert "vacaciones" in prompt_text
