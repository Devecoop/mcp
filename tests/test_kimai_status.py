"""Tests for the read-only ``kimai_status`` tool."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pytest
from mcp.types import CallToolResult

from devecoop_mcp.config import Settings
from devecoop_mcp.core.errors import ConfigurationError
from devecoop_mcp.server import create_server

STATUS_PAYLOADS: dict[str, object] = {
    "/api/version": {
        "version": "1.22.1",
        "versionId": 12201,
        "candidate": "prod",
        "semver": "1.22.1-prod",
        "name": "Kimai",
        "copyright": "Kimai",
    },
    "/api/users/me": {
        "id": 1,
        "username": "MCP-test",
        "alias": "MCP test",
        "timezone": "Europe/Berlin",
        "enabled": True,
        "roles": ["ROLE_USER"],
    },
    "/api/config/timesheet": {
        "trackingMode": "default",
        "defaultBeginTime": "09:00",
        "activeEntriesHardLimit": 1,
        "activeEntriesSoftLimit": 1,
        "isAllowFutureTimes": False,
        "isAllowOverlapping": False,
    },
    "/api/users": [
        {
            "id": 1,
            "username": "MCP-test",
            "alias": "MCP test",
            "accountNumber": None,
            "enabled": True,
            "color": "#dd1d00",
        }
    ],
}


def _fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    path = urllib.parse.urlsplit(request.full_url).path
    if path in STATUS_PAYLOADS:
        return 200, json.dumps(STATUS_PAYLOADS[path]).encode("utf-8")
    return 404, b'{"message": "Not Found"}'


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        kimai_url="https://kimai.example.com",
        kimai_api_user="MCP-test",
        kimai_api_token="super-secret-token",
        kimai_default_user="MCP-test",
        kimai_default_begin_time="09:00",
    )


async def test_kimai_status_returns_configured_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("devecoop_mcp.kimai.client._default_transport", _fake_transport)
    server = create_server(_make_settings())

    result = await server.call_tool("kimai_status", {})

    assert isinstance(result, CallToolResult)
    payload = result.structured_content
    assert payload is not None
    assert payload["version"]["version"] == "1.22.1"
    assert payload["api_user"]["username"] == "MCP-test"
    assert payload["default_user"]["username"] == "MCP-test"
    assert payload["timesheet_config"]["tracking_mode"] == "default"
    assert payload["default_begin_time"] == "09:00"


async def test_kimai_status_is_registered_when_configured() -> None:
    server = create_server(_make_settings())

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "kimai_status" in tool_names
    assert server.instructions is not None
    assert "kimai_status" in server.instructions
    assert "KIMAI_DEFAULT_USER" in server.instructions


def test_create_server_requires_a_configured_feature() -> None:
    settings = Settings(
        _env_file=None,
        wiki_path=None,
        kimai_url=None,
        kimai_api_user=None,
        kimai_api_token=None,
        kimai_default_user=None,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        create_server(settings)

    message = str(exc_info.value)
    assert "WIKI_PATH" in message
    assert "KIMAI_URL" in message


def test_partial_kimai_configuration_lists_missing_variables() -> None:
    settings = Settings(
        _env_file=None,
        kimai_url="https://kimai.example.com",
        kimai_api_user=None,
        kimai_api_token=None,
        kimai_default_user=None,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        settings.kimai_config()

    message = str(exc_info.value)
    assert "KIMAI_API_USER" in message
    assert "KIMAI_API_TOKEN" in message
    assert "KIMAI_DEFAULT_USER" in message
