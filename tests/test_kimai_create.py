"""Tests for the Kimai preview and log write flow."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import SecretStr

from devecoop_mcp.config import KimaiConfig, Settings
from devecoop_mcp.core.errors import KimaiError, KimaiUnavailableError
from devecoop_mcp.kimai.client import KimaiClient
from devecoop_mcp.kimai.models import KimaiTimesheetDraft
from devecoop_mcp.kimai.timesheets import log_timesheets, preview_timesheets
from devecoop_mcp.kimai.tokens import create_token, read_token
from devecoop_mcp.server import create_server

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


def _existing_entry(
    entry_id: int = 77,
    begin: str = "2026-11-19T09:00:00-0300",
    end: str = "2026-11-19T14:00:00-0300",
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "begin": begin,
        "end": end,
        "duration": 18000,
        "description": description,
        "user": 7,
        "project": {"id": 3, "name": "Internal Tools"},
        "activity": {"id": 5, "name": "Development"},
    }


@dataclass
class FakeKimai:
    """In-memory Kimai API used as the client transport in tests."""

    existing_entries: list[dict[str, Any]] = field(default_factory=list)
    project: dict[str, Any] = field(default_factory=lambda: dict(PROJECT))
    activity: dict[str, Any] = field(default_factory=lambda: dict(ACTIVITY))
    post_failures: dict[int, tuple[int, bytes] | Exception] = field(default_factory=dict)
    timeout_recoveries: dict[int, dict[str, Any]] = field(default_factory=dict)
    requests: list[urllib.request.Request] = field(default_factory=list)
    post_payloads: list[dict[str, Any]] = field(default_factory=list)
    post_count: int = 0

    def __call__(
        self,
        request: urllib.request.Request,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.requests.append(request)
        path = urllib.parse.urlsplit(request.full_url).path
        if path == "/api/users":
            return self._json([DEFAULT_USER])
        if path == "/api/users/me":
            return self._json(API_USER)
        if path == "/api/projects":
            return self._json([self.project])
        if path == f"/api/projects/{self.project['id']}":
            return self._json(self.project)
        if path == "/api/activities":
            return self._json([self.activity])
        if path == f"/api/activities/{self.activity['id']}":
            return self._json(self.activity)
        if path == "/api/timesheets":
            if request.method == "GET":
                return self._json(self.existing_entries)
            if request.method == "POST":
                return self._create(request)
        return 404, b'{"message": "Not Found"}'

    def _create(self, request: urllib.request.Request) -> tuple[int, bytes]:
        self.post_count += 1
        raw_payload = json.loads(request.data or b"{}")
        assert isinstance(raw_payload, dict)
        payload: dict[str, Any] = raw_payload
        self.post_payloads.append(payload)

        failure = self.post_failures.get(self.post_count)
        if isinstance(failure, Exception):
            recovery = self.timeout_recoveries.get(self.post_count)
            if recovery is not None:
                self.existing_entries.append(recovery)
            raise failure
        if failure is not None:
            return failure

        begin_datetime = datetime.fromisoformat(payload["begin"])
        end_datetime = datetime.fromisoformat(payload["end"])
        created = {
            "id": 100 + self.post_count,
            "begin": f"{payload['begin']}-0300",
            "end": f"{payload['end']}-0300",
            "duration": int((end_datetime - begin_datetime).total_seconds()),
            "description": payload.get("description"),
            "user": payload["user"],
            "project": {"id": payload["project"], "name": self.project["name"]},
            "activity": {"id": payload["activity"], "name": self.activity["name"]},
        }
        self.existing_entries.append(created)
        return self._json(created)

    @staticmethod
    def _json(payload: object) -> tuple[int, bytes]:
        return 200, json.dumps(payload).encode("utf-8")


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


def _preview(
    fake: FakeKimai,
    entries: list[KimaiTimesheetDraft],
    description: str | None = None,
):
    config = _make_config()
    return preview_timesheets(
        KimaiClient(config, transport=fake),
        config,
        "Internal Tools",
        "Development",
        entries,
        description=description,
    )


def _log(fake: FakeKimai, confirmation_token: str):
    config = _make_config()
    return log_timesheets(
        KimaiClient(config, transport=fake),
        config,
        confirmation_token,
    )


def _post_requests(fake: FakeKimai) -> list[urllib.request.Request]:
    return [request for request in fake.requests if request.method == "POST"]


def test_preview_single_entry_with_duration() -> None:
    fake = FakeKimai()

    response = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])

    assert response.entries[0].begin == "2026-11-19T09:00:00"
    assert response.entries[0].end == "2026-11-19T14:00:00"
    assert response.entries[0].duration_minutes == 300
    assert response.total_duration_minutes == 300
    assert "alice" in response.summary
    assert "Internal Tools" in response.summary
    assert "Development" in response.summary
    assert "- 2026-11-19: 5 h (09:00–14:00)" in response.summary  # noqa: RUF001
    assert "Total: 5 h" in response.summary
    assert response.confirmation_token
    assert response.expires_at
    assert _post_requests(fake) == []


def test_preview_explicit_begin_and_end() -> None:
    fake = FakeKimai()

    response = _preview(
        fake,
        [KimaiTimesheetDraft(date="2026-11-19", begin="14:00", end="17:00")],
    )

    assert response.entries[0].begin == "2026-11-19T14:00:00"
    assert response.entries[0].end == "2026-11-19T17:00:00"
    assert response.entries[0].duration_minutes == 180
    assert "3 h" in response.summary


def test_preview_batch_builds_one_token_and_total() -> None:
    fake = FakeKimai()
    entries = [
        KimaiTimesheetDraft(date="2026-11-19", duration_minutes=360),
        KimaiTimesheetDraft(date="2026-11-20", duration_minutes=360),
    ]

    response = _preview(fake, entries)

    assert response.total_duration_minutes == 720
    assert [entry.date for entry in response.entries] == ["2026-11-19", "2026-11-20"]
    assert "- 2026-11-19: 6 h (09:00–15:00)" in response.summary  # noqa: RUF001
    assert "- 2026-11-20: 6 h (09:00–15:00)" in response.summary  # noqa: RUF001
    assert "Total: 12 h" in response.summary

    token_payload = read_token(response.confirmation_token)
    assert len(token_payload["entries"]) == 2
    assert _post_requests(fake) == []


def test_preview_rejects_empty_batch() -> None:
    with pytest.raises(ValueError, match="between 1 and 31"):
        _preview(FakeKimai(), [])


def test_preview_rejects_batch_over_limit() -> None:
    entries = [KimaiTimesheetDraft(date="2026-11-01", duration_minutes=60)] * 32

    with pytest.raises(ValueError, match="between 1 and 31"):
        _preview(FakeKimai(), entries)


def test_preview_rejects_end_and_duration_together() -> None:
    draft = KimaiTimesheetDraft(
        date="2026-11-19",
        begin="09:00",
        end="10:00",
        duration_minutes=60,
    )

    with pytest.raises(ValueError, match="Provide either end or duration_minutes, not both"):
        _preview(FakeKimai(), [draft])


def test_preview_rejects_missing_end_and_duration() -> None:
    with pytest.raises(ValueError, match="Provide end or duration_minutes"):
        _preview(FakeKimai(), [KimaiTimesheetDraft(date="2026-11-19")])


def test_preview_rejects_end_before_begin() -> None:
    draft = KimaiTimesheetDraft(date="2026-11-19", begin="15:00", end="14:00")

    with pytest.raises(ValueError, match="end must be after begin"):
        _preview(FakeKimai(), [draft])


def test_preview_rejects_overnight_duration() -> None:
    draft = KimaiTimesheetDraft(date="2026-11-19", begin="23:00", duration_minutes=120)

    with pytest.raises(ValueError, match="must not cross midnight"):
        _preview(FakeKimai(), [draft])


@pytest.mark.parametrize("invalid_date", ["2026-02-30", "2026-13-01", "19-11-2026"])
def test_preview_rejects_invalid_date(invalid_date: str) -> None:
    with pytest.raises(ValueError):
        _preview(
            FakeKimai(),
            [KimaiTimesheetDraft(date=invalid_date, duration_minutes=60)],
        )


@pytest.mark.parametrize("invalid_time", ["25:00", "9:00", "09:60"])
def test_preview_rejects_invalid_time(invalid_time: str) -> None:
    with pytest.raises(ValueError):
        _preview(
            FakeKimai(),
            [KimaiTimesheetDraft(date="2026-11-19", begin=invalid_time, duration_minutes=60)],
        )


def test_preview_rejects_activity_from_another_project() -> None:
    fake = FakeKimai(activity={**ACTIVITY, "project": 9})

    with pytest.raises(ValueError, match="belongs to project") as exc_info:
        _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=60)])

    message = str(exc_info.value)
    assert "Development" in message
    assert "Internal Tools" in message


def test_preview_rejects_existing_duplicate() -> None:
    fake = FakeKimai(existing_entries=[_existing_entry()])

    with pytest.raises(ValueError, match="already exists") as exc_info:
        _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])

    message = str(exc_info.value)
    assert "77" in message
    assert "2026-11-19" in message
    assert "09:00" in message
    assert "14:00" in message
    assert _post_requests(fake) == []


def test_preview_rejects_duplicate_within_batch() -> None:
    entries = [
        KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300),
        KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300),
    ]

    with pytest.raises(ValueError, match="Duplicate entry within the batch"):
        _preview(FakeKimai(), entries)


def test_log_writes_all_entries_and_payload_fields() -> None:
    fake = FakeKimai()
    preview = _preview(
        fake,
        [
            KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300),
            KimaiTimesheetDraft(date="2026-11-20", duration_minutes=180),
        ],
        description="Work",
    )

    response = _log(fake, preview.confirmation_token)

    assert response.status == "ok"
    assert [entry.id for entry in response.written] == [101, 102]
    assert response.written[0].project_name == "Internal Tools"
    assert response.written[0].activity_name == "Development"
    assert response.written[0].description == "Work"
    assert response.failed_entry is None
    assert response.pending == []
    assert response.error is None

    assert len(fake.post_payloads) == 2
    for payload in fake.post_payloads:
        assert payload["user"] == 7
        assert payload["project"] == 3
        assert payload["activity"] == 5
        assert payload["description"] == "Work"
        assert "begin" in payload
        assert "end" in payload
        assert "duration" not in payload


def test_log_rejects_tampered_token_without_posting() -> None:
    fake = FakeKimai()
    preview = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])
    encoded_payload, encoded_signature = preview.confirmation_token.split(".")
    replacement = "A" if encoded_signature[0] != "A" else "B"
    tampered = f"{encoded_payload}.{replacement}{encoded_signature[1:]}"

    with pytest.raises(ValueError, match="Invalid or expired preview token"):
        _log(fake, tampered)

    assert _post_requests(fake) == []


def test_log_rejects_expired_token_without_posting() -> None:
    fake = FakeKimai()
    preview = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])
    token_payload = read_token(preview.confirmation_token)
    expired = create_token(token_payload, ttl_seconds=-1)

    with pytest.raises(ValueError, match="Invalid or expired preview token"):
        _log(fake, expired)

    assert _post_requests(fake) == []


def test_log_rejects_token_for_a_different_user_without_posting() -> None:
    fake = FakeKimai()
    token = create_token(
        {
            "kind": "create",
            "v": 1,
            "user_id": 999,
            "project_id": 3,
            "project_name": "Internal Tools",
            "activity_id": 5,
            "activity_name": "Development",
            "description": None,
            "entries": [{"begin": "2026-11-19T09:00:00", "end": "2026-11-19T14:00:00"}],
        }
    )

    with pytest.raises(ValueError, match="different user"):
        _log(fake, token)

    assert _post_requests(fake) == []


def test_log_rejects_duplicate_created_after_preview() -> None:
    fake = FakeKimai()
    preview = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])
    fake.existing_entries.append(_existing_entry(entry_id=88))

    with pytest.raises(KimaiError, match="already exists") as exc_info:
        _log(fake, preview.confirmation_token)

    assert "88" in str(exc_info.value)
    assert _post_requests(fake) == []


def test_log_reports_partial_failure() -> None:
    fake = FakeKimai()
    preview = _preview(
        fake,
        [
            KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300),
            KimaiTimesheetDraft(date="2026-11-20", duration_minutes=300),
            KimaiTimesheetDraft(date="2026-11-21", duration_minutes=300),
        ],
    )
    fake.post_failures[2] = (400, json.dumps({"message": "Invalid entry"}).encode("utf-8"))

    response = _log(fake, preview.confirmation_token)

    assert response.status == "partial"
    assert [entry.id for entry in response.written] == [101]
    assert response.failed_entry is not None
    assert response.failed_entry.begin == "2026-11-20T09:00:00"
    assert [entry.begin for entry in response.pending] == ["2026-11-21T09:00:00"]
    assert response.error is not None
    assert "Invalid entry" in response.error
    assert len(fake.post_payloads) == 2


def test_log_recovers_when_timed_out_entry_was_created() -> None:
    fake = FakeKimai()
    preview = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])
    fake.post_failures[1] = KimaiUnavailableError("timed out")
    fake.timeout_recoveries[1] = _existing_entry(entry_id=555)

    response = _log(fake, preview.confirmation_token)

    assert response.status == "ok"
    assert [entry.id for entry in response.written] == [555]
    assert response.failed_entry is None
    assert response.pending == []
    assert response.error is None


def test_log_reports_unknown_outcome_when_timeout_entry_is_missing() -> None:
    fake = FakeKimai()
    preview = _preview(fake, [KimaiTimesheetDraft(date="2026-11-19", duration_minutes=300)])
    fake.post_failures[1] = KimaiUnavailableError("timed out")

    response = _log(fake, preview.confirmation_token)

    assert response.status == "failed"
    assert response.written == []
    assert response.failed_entry is not None
    assert response.failed_entry.begin == "2026-11-19T09:00:00"
    assert response.error is not None
    assert "unknown" in response.error
    assert "Check Kimai" in response.error


async def test_write_tools_are_registered_when_configured() -> None:
    server = create_server(_make_settings())

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "kimai_preview_timesheets" in tool_names
    assert "kimai_log_timesheets" in tool_names
    assert server.instructions is not None
    assert "kimai_log_timesheets" in server.instructions


async def test_preview_tool_reports_real_validation_error() -> None:
    server = create_server(_make_settings())

    with pytest.raises(ToolError, match="between 1 and 31"):
        await server.call_tool(
            "kimai_preview_timesheets",
            {"project": "Internal Tools", "activity": "Development", "entries": []},
        )
