"""Smoke tests for the Devecoop MCP scaffold."""

from __future__ import annotations

import pytest

import devecoop_mcp
from devecoop_mcp.cli import main
from devecoop_mcp.server import create_server


def test_package_exposes_version() -> None:
    assert devecoop_mcp.__version__ == "0.1.0"


def test_server_is_configured() -> None:
    server = create_server()

    assert server.name == "devecoop"
    assert server.version == "0.1.0"
    assert "GitLab URL" in (server.instructions or "")
    assert "untrusted data" in (server.instructions or "").lower()


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_help_works_without_wiki_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("WIKI_PATH", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "serve" in capsys.readouterr().out
