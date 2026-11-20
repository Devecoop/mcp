"""MCP tools for the Kimai integration.

Only the read-only ``kimai_status`` tool is exposed in this increment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.types import ToolAnnotations

from devecoop_mcp.kimai.models import (
    KimaiStatusResponse,
    KimaiTimesheetConfigSummary,
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
