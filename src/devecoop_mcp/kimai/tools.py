"""MCP tools for the Kimai integration.

The read-only ``kimai_status`` and ``kimai_list_timesheets`` tools are exposed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.types import ToolAnnotations

from devecoop_mcp.kimai.models import (
    KimaiStatusResponse,
    KimaiTimesheetConfigSummary,
    KimaiTimesheetEntry,
    KimaiTimesheetListResponse,
    KimaiUserSummary,
    KimaiVersionSummary,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from devecoop_mcp.config import KimaiConfig
    from devecoop_mcp.kimai.client import KimaiClient


TOOL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)

KIMAI_STATUS_DESCRIPTION = (
    "Return Kimai version, API user, configured target user and timesheet configuration. Read-only."
)

KIMAI_LIST_TIMESHEETS_DESCRIPTION = (
    "List the configured user's own Kimai timesheets in a date range "
    "(default: current month; dates use YYYY-MM-DD). Optionally filter by "
    "project, activity or description. Read-only."
)


def _current_date(timezone_name: object) -> date:
    """Return today's date in the API user timezone, falling back to local time."""
    if isinstance(timezone_name, str) and timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return date.today()


def _user_summary(payload: dict[str, Any]) -> KimaiUserSummary:
    """Map a Kimai user entity to the tool output model."""
    return KimaiUserSummary(
        id=int(payload["id"]),
        username=str(payload["username"]),
        alias=payload.get("alias"),
        timezone=payload.get("timezone"),
        enabled=payload.get("enabled"),
        roles=payload.get("roles") or [],
    )


def _timesheet_config_summary(payload: dict[str, Any]) -> KimaiTimesheetConfigSummary:
    """Map Kimai camelCase timesheet fields to the snake_case output model."""
    return KimaiTimesheetConfigSummary(
        tracking_mode=str(payload["trackingMode"]),
        default_begin_time=str(payload["defaultBeginTime"]),
        allow_future_times=payload["isAllowFutureTimes"],
        allow_overlapping=payload["isAllowOverlapping"],
        active_entries_hard_limit=payload.get("activeEntriesHardLimit"),
        active_entries_soft_limit=payload.get("activeEntriesSoftLimit"),
    )


def _timesheet_entry(payload: dict[str, Any]) -> KimaiTimesheetEntry:
    """Map a full Kimai timesheet entry to the tool output model."""
    project = payload["project"]
    activity = payload["activity"]
    return KimaiTimesheetEntry(
        id=int(payload["id"]),
        begin=str(payload["begin"]),
        end=payload.get("end"),
        duration_minutes=round(int(payload["duration"]) / 60),
        project_id=int(project["id"]),
        project_name=str(project["name"]),
        activity_id=int(activity["id"]),
        activity_name=str(activity["name"]),
        description=payload.get("description"),
    )


def list_own_timesheets(
    client: KimaiClient,
    config: KimaiConfig,
    from_date: str | None = None,
    to_date: str | None = None,
    project: str | None = None,
    activity: str | None = None,
    term: str | None = None,
    limit: int = 100,
) -> KimaiTimesheetListResponse:
    """List the configured user's own Kimai timesheets in a date range."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    default_user_payload = client.resolve_user(config.default_user)
    user_id = int(default_user_payload["id"])

    project_id = int(client.resolve_project(project)["id"]) if project is not None else None
    activity_id = int(client.resolve_activity(activity)["id"]) if activity is not None else None

    api_user_payload = client.get_current_user()
    today = _current_date(api_user_payload.get("timezone"))

    effective_to = date.fromisoformat(to_date) if to_date is not None else today
    effective_from = (
        date.fromisoformat(from_date) if from_date is not None else effective_to.replace(day=1)
    )
    if effective_from > effective_to:
        raise ValueError("from_date must be on or before to_date")

    payload = client.list_timesheets(
        user_id,
        f"{effective_from.isoformat()}T00:00:00",
        f"{effective_to.isoformat()}T23:59:59",
        project_id=project_id,
        activity_id=activity_id,
        term=term,
        limit=limit,
    )
    entries = [_timesheet_entry(entry) for entry in payload]
    return KimaiTimesheetListResponse(
        user=_user_summary(default_user_payload),
        from_date=effective_from.isoformat(),
        to_date=effective_to.isoformat(),
        entries=entries,
        count=len(entries),
        total_duration_minutes=sum(entry.duration_minutes for entry in entries),
        truncated=len(entries) == limit,
    )


def register_tools(mcp: MCPServer, client: KimaiClient, config: KimaiConfig) -> None:
    """Register the Kimai tools on ``mcp``.

    Args:
        mcp: The Devecoop MCP server instance.
        client: Kimai API client.
        config: Validated Kimai configuration.
    """

    @mcp.tool(annotations=TOOL_ANNOTATIONS, description=KIMAI_STATUS_DESCRIPTION)
    def kimai_status() -> KimaiStatusResponse:
        """Report the configured Kimai instance status."""
        version_payload = client.get_version()
        api_user_payload = client.get_current_user()
        timesheet_payload = client.get_timesheet_config()
        default_user_payload = client.resolve_user(config.default_user)

        return KimaiStatusResponse(
            base_url=config.base_url,
            version=KimaiVersionSummary(
                version=str(version_payload["version"]),
                semver=version_payload.get("semver"),
                name=version_payload.get("name"),
            ),
            api_user=_user_summary(api_user_payload),
            default_user=_user_summary(default_user_payload),
            timesheet_config=_timesheet_config_summary(timesheet_payload),
            default_begin_time=config.default_begin_time,
        )

    @mcp.tool(
        annotations=TOOL_ANNOTATIONS,
        description=KIMAI_LIST_TIMESHEETS_DESCRIPTION,
    )
    def kimai_list_timesheets(
        from_date: str | None = None,
        to_date: str | None = None,
        project: str | None = None,
        activity: str | None = None,
        term: str | None = None,
        limit: int = 100,
    ) -> KimaiTimesheetListResponse:
        """List the configured user's own timesheets."""
        return list_own_timesheets(
            client,
            config,
            from_date=from_date,
            to_date=to_date,
            project=project,
            activity=activity,
            term=term,
            limit=limit,
        )
