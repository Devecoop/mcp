"""Tests for the read-only ``kimai_list_timesheets`` tool."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable

import pytest
from pydantic import SecretStr

from devecoop_mcp.config import KimaiConfig, Settings
from devecoop_mcp.kimai.client import KimaiClient
from devecoop_mcp.kimai.tools import list_own_timesheets
from devecoop_mcp.server import create_server

Transport = Callable[[urllib.request.Request, float], tuple[int, bytes]]

API_USER = {
    "id": 1,
    "username": "MCP-test",
    "alias": "MCP test",
    "timezone": "Europe/Berlin",
    "enabled": True,
    "roles": ["ROLE_USER"],
}
DEFAULT_USER = {
    "id": 7,
    "username": "alice",
    "alias": "Alice",
    "timezone": "Europe/Berlin",
    "enabled": True,
    "roles": ["ROLE_USER"],
}
PROJECT = {"id": 3, "name": "Internal Tools", "customer": 1, "parentTitle": "Acme"}
ACTIVITY = {"id": 5, "name": "Development", "project": 3, "parentTitle": "Internal Tools"}
TIMESHEETS = [
    {
        "id": 101,
        "begin": "2026-05-12T09:00:00+0200",
        "end": "2026-05-12T10:30:00+0200",
        "duration": 5400,
        "description": "Reviewed pull request",
        "user": 7,
        "project": {"id": 3, "name": "Internal Tools"},
        "activity": {"id": 5, "name": "Development"},
    },
    {
        "id": 102,
        "begin": "2026-05-13T09:00:00+0200",
        "end": None,
        "duration": 1800,
        "description": None,
        "user": 7,
        "project": {"id": 3, "name": "Internal Tools"},
        "activity": {"id": 5, "name": "Development"},
    },
]


def _make_config() -> KimaiConfig:
    return KimaiConfig(
        base_url="https://kimai.example.com",
        api_user="MCP-test",
        api_token=SecretStr("super-secret-token"),
        default_user="alice",
        default_begin_time="09:00",
    )


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        kimai_url="https://kimai.example.com",
        kimai_api_user="MCP-test",
        kimai_api_token="super-secret-token",
        kimai_default_user="alice",
        kimai_default_begin_time="09:00",
    )


def _make_transport(requests: list[urllib.request.Request]) -> Transport:
    payloads: dict[str, object] = {
        "/api/users/me": API_USER,
        "/api/users": [DEFAULT_USER],
        "/api/projects": [PROJECT],
        "/api/activities": [ACTIVITY],
        "/api/timesheets": TIMESHEETS,
    }

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        path = urllib.parse.urlsplit(request.full_url).path
        if path not in payloads:
            return 404, b'{"message": "Not Found"}'
        return 200, json.dumps(payloads[path]).encode("utf-8")

    return fake_transport


def test_list_own_timesheets_maps_entries_and_filters() -> None:
    requests: list[urllib.request.Request] = []
    config = _make_config()
    client = KimaiClient(config, transport=_make_transport(requests))

    response = list_own_timesheets(
        client,
        config,
        from_date="2026-05-01",
        to_date="2026-05-31",
        project="Internal Tools",
        activity="Development",
        term="review",
        limit=2,
    )

    assert response.user.id == 7
    assert response.user.username == "alice"
    assert response.from_date == "2026-05-01"
    assert response.to_date == "2026-05-31"
    assert response.count == 2
    assert response.total_duration_minutes == 120
    assert response.truncated is True

    first_entry = response.entries[0]
    assert first_entry.id == 101
    assert first_entry.begin == "2026-05-12T09:00:00+0200"
    assert first_entry.end == "2026-05-12T10:30:00+0200"
    assert first_entry.duration_minutes == 90
    assert first_entry.project_id == 3
    assert first_entry.project_name == "Internal Tools"
    assert first_entry.activity_id == 5
    assert first_entry.activity_name == "Development"
    assert first_entry.description == "Reviewed pull request"

    second_entry = response.entries[1]
    assert second_entry.end is None
    assert second_entry.duration_minutes == 30
    assert second_entry.description is None

    timesheet_request = next(
        request
        for request in requests
        if urllib.parse.urlsplit(request.full_url).path == "/api/timesheets"
    )
    parameters = urllib.parse.parse_qs(urllib.parse.urlsplit(timesheet_request.full_url).query)
    assert parameters["user"] == ["7"]
    assert parameters["user"] != ["all"]
    assert parameters["begin"] == ["2026-05-01T00:00:00"]
    assert parameters["end"] == ["2026-05-31T23:59:59"]
    assert parameters["size"] == ["2"]
    assert parameters["projects"] == ["3"]
    assert parameters["activities"] == ["5"]
    assert parameters["term"] == ["review"]


def test_list_own_timesheets_rejects_inverted_date_range() -> None:
    requests: list[urllib.request.Request] = []
    config = _make_config()
    client = KimaiClient(config, transport=_make_transport(requests))

    with pytest.raises(ValueError, match="from_date must be on or before to_date"):
        list_own_timesheets(
            client,
            config,
            from_date="2026-05-31",
            to_date="2026-05-01",
        )


@pytest.mark.parametrize("limit", [0, 501])
def test_list_own_timesheets_rejects_limit_outside_supported_range(limit: int) -> None:
    requests: list[urllib.request.Request] = []
    config = _make_config()
    client = KimaiClient(config, transport=_make_transport(requests))

    with pytest.raises(ValueError, match="limit must be between 1 and 500"):
        list_own_timesheets(
            client,
            config,
            from_date="2026-05-01",
            to_date="2026-05-31",
            limit=limit,
        )


async def test_kimai_list_timesheets_is_registered_when_configured() -> None:
    server = create_server(_make_settings())

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "kimai_list_timesheets" in tool_names
    assert server.instructions is not None
    assert "kimai_list_timesheets" in server.instructions
    assert "KIMAI_DEFAULT_USER" in server.instructions
