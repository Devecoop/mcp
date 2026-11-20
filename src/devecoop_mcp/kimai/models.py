"""Pydantic models for the Kimai tool contracts."""

from __future__ import annotations

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
