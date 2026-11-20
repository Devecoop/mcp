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
PROJECT_PAYLOAD = {
    "id": 3,
    "name": "Internal Tools",
    "customer": 1,
    "parentTitle": "Acme",
}
ACTIVITY_PAYLOAD = {
    "id": 5,
    "name": "Development",
    "project": 3,
    "parentTitle": "Internal Tools",
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


def test_list_timesheets_sends_expected_query_parameters() -> None:
    requests: list[urllib.request.Request] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        return 200, b"[]"

    client = KimaiClient(_make_config(), transport=fake_transport)

    result = client.list_timesheets(
        7,
        "2026-05-01T00:00:00",
        "2026-05-31T23:59:59",
        project_id=3,
        activity_id=5,
        term="review",
        limit=50,
    )

    assert result == []
    url = urllib.parse.urlsplit(requests[0].full_url)
    assert url.path == "/api/timesheets"
    assert urllib.parse.parse_qs(url.query) == {
        "user": ["7"],
        "begin": ["2026-05-01T00:00:00"],
        "end": ["2026-05-31T23:59:59"],
        "size": ["50"],
        "orderBy": ["begin"],
        "order": ["ASC"],
        "full": ["true"],
        "projects": ["3"],
        "activities": ["5"],
        "term": ["review"],
    }


def test_list_timesheets_omits_optional_filters() -> None:
    requests: list[urllib.request.Request] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        return 200, b"[]"

    client = KimaiClient(_make_config(), transport=fake_transport)

    client.list_timesheets(7, "2026-05-01T00:00:00", "2026-05-31T23:59:59")

    url = urllib.parse.urlsplit(requests[0].full_url)
    assert urllib.parse.parse_qs(url.query) == {
        "user": ["7"],
        "begin": ["2026-05-01T00:00:00"],
        "end": ["2026-05-31T23:59:59"],
        "size": ["100"],
        "orderBy": ["begin"],
        "order": ["ASC"],
        "full": ["true"],
    }


def test_resolve_project_matches_exact_name_and_numeric_id() -> None:
    requests: list[urllib.request.Request] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        return 200, json.dumps([PROJECT_PAYLOAD]).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    assert client.resolve_project("INTERNAL TOOLS")["id"] == 3
    assert client.resolve_project("3") == {"id": 3}

    url = urllib.parse.urlsplit(requests[0].full_url)
    assert url.path == "/api/projects"
    assert urllib.parse.parse_qs(url.query) == {
        "visible": ["1"],
        "ignoreDates": ["1"],
        "term": ["INTERNAL TOOLS"],
    }


def test_resolve_activity_matches_exact_name() -> None:
    requests: list[urllib.request.Request] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        requests.append(request)
        return 200, json.dumps([ACTIVITY_PAYLOAD]).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    assert client.resolve_activity("development")["id"] == 5

    url = urllib.parse.urlsplit(requests[0].full_url)
    assert url.path == "/api/activities"
    assert urllib.parse.parse_qs(url.query) == {
        "visible": ["1"],
        "term": ["development"],
    }


def test_resolve_project_reports_ambiguous_matches_with_parent_title() -> None:
    projects = [
        {**PROJECT_PAYLOAD, "id": 3, "name": "Shared", "parentTitle": "Acme"},
        {**PROJECT_PAYLOAD, "id": 4, "name": "Shared", "parentTitle": "Beta"},
    ]

    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, json.dumps(projects).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError) as exc_info:
        client.resolve_project("shared")

    message = str(exc_info.value)
    assert "id=3" in message
    assert "Acme" in message
    assert "id=4" in message
    assert "Beta" in message


def test_resolve_project_reports_candidates_for_partial_name() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, json.dumps([PROJECT_PAYLOAD]).encode("utf-8")

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError) as exc_info:
        client.resolve_project("internal")

    message = str(exc_info.value)
    assert "Candidates" in message
    assert "id=3" in message
    assert "Internal Tools" in message


def test_resolve_project_raises_for_unknown_name() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, b"[]"

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError, match="No Kimai project matches"):
        client.resolve_project("nobody")


def test_resolve_activity_raises_for_unknown_name() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        return 200, b"[]"

    client = KimaiClient(_make_config(), transport=fake_transport)

    with pytest.raises(KimaiError, match="No Kimai activity matches"):
        client.resolve_activity("nobody")
