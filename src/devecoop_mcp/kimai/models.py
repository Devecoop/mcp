"""Pydantic models for the Kimai tool contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KimaiVersionSummary(BaseModel):
    """Kimai release information."""

    version: str = Field(description="Kimai version, for example '1.22.1'.")
    semver: str | None = Field(
        default=None,
        description="Full version including status, for example '1.22.1-prod'.",
    )
    name: str | None = Field(default=None, description="Version name.")


class KimaiUserSummary(BaseModel):
    """A Kimai user with the fields needed by the tools."""

    id: int = Field(description="Kimai internal user ID.")
    username: str = Field(description="Kimai username.")
    alias: str | None = Field(default=None, description="Display alias, if configured.")
    timezone: str | None = Field(default=None, description="User timezone.")
    enabled: bool | None = Field(default=None, description="Whether the user is enabled.")
    roles: list[str] = Field(default_factory=list, description="Kimai role names.")


def kimai_user_summary(payload: dict[str, Any]) -> KimaiUserSummary:
    """Map a Kimai user entity to the tool output model."""
    return KimaiUserSummary(
        id=int(payload["id"]),
        username=str(payload["username"]),
        alias=payload.get("alias"),
        timezone=payload.get("timezone"),
        enabled=payload.get("enabled"),
        roles=payload.get("roles") or [],
    )


class KimaiTimesheetConfigSummary(BaseModel):
    """Instance-wide timesheet configuration."""

    tracking_mode: str = Field(description="Kimai time-tracking mode.")
    default_begin_time: str = Field(
        description="Default begin time reported by Kimai (may be a date expression)."
    )
    allow_future_times: bool = Field(description="Whether entries for future times are allowed.")
    allow_overlapping: bool = Field(description="Whether overlapping entries are allowed.")
    active_entries_hard_limit: int | None = Field(
        default=None,
        description="Maximum number of simultaneously running timesheets.",
    )
    active_entries_soft_limit: int | None = Field(
        default=None,
        description="Running timesheet count that triggers a warning.",
    )


class KimaiStatusResponse(BaseModel):
    """Result of a ``kimai_status`` call."""

    base_url: str = Field(description="Normalized Kimai base URL.")
    version: KimaiVersionSummary = Field(description="Kimai release information.")
    api_user: KimaiUserSummary = Field(
        description="User authenticated by the configured API credentials."
    )
    default_user: KimaiUserSummary = Field(description="User resolved from KIMAI_DEFAULT_USER.")
    timesheet_config: KimaiTimesheetConfigSummary = Field(
        description="Timesheet configuration of the Kimai instance."
    )
    default_begin_time: str = Field(description="Configured default begin time for new timesheets.")


class KimaiTimesheetEntry(BaseModel):
    """A single Kimai timesheet entry."""

    id: int = Field(description="Kimai internal timesheet ID.")
    begin: str = Field(description="Begin timestamp as returned by Kimai, including its offset.")
    end: str | None = Field(
        default=None,
        description="End timestamp as returned by Kimai, or null while the entry is running.",
    )
    duration_minutes: int = Field(description="Duration in minutes, rounded from API seconds.")
    project_id: int = Field(description="Kimai project ID.")
    project_name: str = Field(description="Kimai project name.")
    activity_id: int = Field(description="Kimai activity ID.")
    activity_name: str = Field(description="Kimai activity name.")
    description: str | None = Field(default=None, description="Timesheet description.")


class KimaiTimesheetListResponse(BaseModel):
    """Result of a ``kimai_list_timesheets`` call."""

    user: KimaiUserSummary = Field(description="Configured target user.")
    from_date: str = Field(description="Effective start date in YYYY-MM-DD format.")
    to_date: str = Field(description="Effective end date in YYYY-MM-DD format.")
    entries: list[KimaiTimesheetEntry] = Field(description="Matching timesheet entries.")
    count: int = Field(description="Number of returned entries.")
    total_duration_minutes: int = Field(
        description="Sum of the returned entry durations in minutes."
    )
    truncated: bool = Field(description="Whether the result reached the requested limit.")


class KimaiTimesheetDraft(BaseModel):
    """Input model for one timesheet entry to preview or create."""

    date: str = Field(description="Entry date in YYYY-MM-DD format.")
    begin: str | None = Field(
        default=None,
        description=(
            "Begin time in 24-hour HH:MM format; defaults to KIMAI_DEFAULT_BEGIN_TIME when omitted."
        ),
    )
    end: str | None = Field(
        default=None,
        description="End time in 24-hour HH:MM format. Provide either end or duration_minutes.",
    )
    duration_minutes: int | None = Field(
        default=None,
        description="Positive duration in minutes. Provide either end or duration_minutes.",
    )


class KimaiPreviewEntry(BaseModel):
    """One normalized entry in a timesheet preview."""

    date: str = Field(description="Entry date in YYYY-MM-DD format.")
    begin: str = Field(description="Local begin datetime in YYYY-MM-DDTHH:MM:SS format.")
    end: str = Field(description="Local end datetime in YYYY-MM-DDTHH:MM:SS format.")
    duration_minutes: int = Field(description="Duration in minutes.")


class KimaiTimesheetPreviewResponse(BaseModel):
    """Result of a ``kimai_preview_timesheets`` call. No entries were written."""

    user: KimaiUserSummary = Field(description="Configured target user.")
    project_id: int = Field(description="Kimai project ID.")
    project_name: str = Field(description="Kimai project name.")
    activity_id: int = Field(description="Kimai activity ID.")
    activity_name: str = Field(description="Kimai activity name.")
    description: str | None = Field(default=None, description="Timesheet description.")
    entries: list[KimaiPreviewEntry] = Field(description="Normalized entries in begin order.")
    total_duration_minutes: int = Field(description="Sum of all entry durations in minutes.")
    summary: str = Field(description="Human-readable confirmation message.")
    confirmation_token: str = Field(description="Signed token required by kimai_log_timesheets.")
    expires_at: str = Field(description="Token expiry as an ISO 8601 UTC timestamp.")


class KimaiWrittenEntry(BaseModel):
    """A timesheet entry created by ``kimai_log_timesheets``."""

    id: int = Field(description="Kimai internal timesheet ID.")
    begin: str = Field(description="Begin timestamp returned by Kimai, including its offset.")
    end: str = Field(description="End timestamp returned by Kimai, including its offset.")
    duration_minutes: int = Field(description="Duration in minutes, rounded from API seconds.")
    project_name: str = Field(description="Kimai project name.")
    activity_name: str = Field(description="Kimai activity name.")
    description: str | None = Field(default=None, description="Timesheet description.")


class KimaiPendingEntry(BaseModel):
    """A timesheet entry that was not confirmed as written."""

    begin: str = Field(description="Local begin datetime in YYYY-MM-DDTHH:MM:SS format.")
    end: str = Field(description="Local end datetime in YYYY-MM-DDTHH:MM:SS format.")
    duration_minutes: int = Field(description="Duration in minutes.")


class KimaiTimesheetLogResponse(BaseModel):
    """Result of a ``kimai_log_timesheets`` call."""

    status: Literal["ok", "partial", "failed"] = Field(
        description="Overall outcome: ok, partial or failed."
    )
    written: list[KimaiWrittenEntry] = Field(description="Entries confirmed as written.")
    failed_entry: KimaiPendingEntry | None = Field(
        default=None,
        description="Entry whose write failed or whose outcome is unknown.",
    )
    pending: list[KimaiPendingEntry] = Field(
        description="Entries after the failed entry that were not attempted."
    )
    error: str | None = Field(default=None, description="Failure explanation, when applicable.")
