"""MCP tools for the Kimai integration.

The read-only ``kimai_status`` and ``kimai_list_timesheets`` tools are exposed
next to the preview/log write flow.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from devecoop_mcp.core.errors import KimaiError
from devecoop_mcp.kimai.models import (
    KimaiStatusResponse,
    KimaiTimesheetConfigSummary,
    KimaiTimesheetDraft,
    KimaiTimesheetEntry,
    KimaiTimesheetListResponse,
    KimaiTimesheetLogResponse,
    KimaiTimesheetPreviewResponse,
    KimaiVersionSummary,
    kimai_user_summary,
)
from devecoop_mcp.kimai.timesheets import log_timesheets, preview_timesheets

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

KIMAI_PREVIEW_TIMESHEETS_DESCRIPTION = (
    "Validate a batch of timesheets for the configured user and return a "
    "human-readable confirmation summary plus a signed token. Does not write."
)

KIMAI_LOG_TIMESHEETS_DESCRIPTION = (
    "Write the timesheets from a preview token. Only call after the human "
    "explicitly confirms the exact preview summary."
)


def _current_date(timezone_name: object) -> date:
    """Return today's date in the API user timezone, falling back to local time."""
    if isinstance(timezone_name, str) and timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return date.today()


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
        user=kimai_user_summary(default_user_payload),
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
        try:
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
                api_user=kimai_user_summary(api_user_payload),
                default_user=kimai_user_summary(default_user_payload),
                timesheet_config=_timesheet_config_summary(timesheet_payload),
                default_begin_time=config.default_begin_time,
            )
        except (KimaiError, ValueError) as error:
            raise ToolError(str(error)) from error

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
        try:
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
        except (KimaiError, ValueError) as error:
            raise ToolError(str(error)) from error

    @mcp.tool(
        annotations=TOOL_ANNOTATIONS,
        description=KIMAI_PREVIEW_TIMESHEETS_DESCRIPTION,
    )
    def kimai_preview_timesheets(
        project: str,
        activity: str,
        entries: list[KimaiTimesheetDraft],
        description: str | None = None,
    ) -> KimaiTimesheetPreviewResponse:
        """Preview a batch of timesheets without writing."""
        try:
            return preview_timesheets(
                client,
                config,
                project,
                activity,
                entries,
                description=description,
            )
        except (KimaiError, ValueError) as error:
            raise ToolError(str(error)) from error

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        description=KIMAI_LOG_TIMESHEETS_DESCRIPTION,
    )
    def kimai_log_timesheets(confirmation_token: str) -> KimaiTimesheetLogResponse:
        """Write timesheets from a confirmed preview."""
        try:
            return log_timesheets(client, config, confirmation_token)
        except (KimaiError, ValueError) as error:
            raise ToolError(str(error)) from error
