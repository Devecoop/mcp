"""Tests for the Kimai API client."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import pytest
from pydantic import SecretStr

from devecoop_mcp.config import KimaiConfig
from devecoop_mcp.core.errors import KimaiError, KimaiUnavailableError
from devecoop_mcp.kimai.client import KimaiClient

TOKEN = "super-secret-token"
USER_PAYLOAD = {
    "id": 7,
    "username": "alice",
    "alias": "Alice Alias",
    "timezone": "Europe/Berlin",
    "enabled": True,
    "roles": ["ROLE_USER"],
}


def _make_config() -> KimaiConfig:
    return KimaiConfig(
        base_url="https://kimai.example.com",
        api_user="MCP-test",
        api_token=SecretStr(TOKEN),
        default_user="alice",
        default_begin_time="09:00",
    )


def test_client_sends_kimai_auth_headers() -> None:
    requests: list[urllib.request.Request] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        return 200, json.dumps({"version": "1.22.1"}).encode("utf-8")

    KimaiClient(_make_config(), transport=fake_transport).get_version()

    assert requests[0].get_header("X-auth-user") == "MCP-test"
    assert requests[0].get_header("X-auth-token") == TOKEN


def test_get_version_parses_response() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, json.dumps(
            {
                "version": "1.22.1",
                "versionId": 12201,
                "candidate": "prod",
                "semver": "1.22.1-prod",
                "name": "Kimai",
            }
        ).encode("utf-8")

    payload = KimaiClient(_make_config(), transport=fake_transport).get_version()

    assert payload["version"] == "1.22.1"
    assert payload["semver"] == "1.22.1-prod"


def test_client_maps_error_response_to_kimai_error() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 403, json.dumps({"message": "Forbidden", "code": 403}).encode("utf-8")

    with pytest.raises(KimaiError) as exc_info:
        KimaiClient(_make_config(), transport=fake_transport).get_version()

    error = exc_info.value
    assert error.status_code == 403
    assert error.details == {"message": "Forbidden", "code": 403}
    assert "Forbidden" in str(error)
    assert TOKEN not in str(error)


@pytest.mark.parametrize(
    "failure",
    [urllib.error.URLError("network down"), TimeoutError("timed out")],
)
def test_default_transport_maps_network_failures(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    def failing_urlopen(request: urllib.request.Request, timeout: float) -> None:
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)

    with pytest.raises(KimaiUnavailableError) as exc_info:
        KimaiClient(_make_config()).get_version()

    assert "Could not reach the Kimai API" in str(exc_info.value)
    assert TOKEN not in str(exc_info.value)


def test_resolve_user_matches_username_alias_and_numeric_id() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        path = urllib.parse.urlsplit(request.full_url).path
        if path == "/api/users":
            return 200, json.dumps([USER_PAYLOAD]).encode("utf-8")
        if path == "/api/users/7":
            return 200, json.dumps(USER_PAYLOAD).encode("utf-8")
        return 404, b'{"message": "Not Found"}'

    client = KimaiClient(_make_config(), transport=fake_transport)

    assert client.resolve_user("ALICE")["id"] == 7
    assert client.resolve_user("alice alias")["id"] == 7
    assert client.resolve_user("7")["id"] == 7


def test_resolve_user_raises_for_unknown_name() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, json.dumps([USER_PAYLOAD]).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError, match="No Kimai user matches"):
        client.resolve_user("nobody")


def test_resolve_user_reports_ambiguous_matches() -> None:
    users = [
        {**USER_PAYLOAD, "id": 7, "username": "alice", "alias": "Shared"},
        {**USER_PAYLOAD, "id": 8, "username": "alicia", "alias": "Shared"},
    ]

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, json.dumps(users).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError) as exc_info:
        client.resolve_user("shared")

    message = str(exc_info.value)
    assert "alice" in message
    assert "alicia" in message
