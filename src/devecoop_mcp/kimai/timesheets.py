"""Preview and log Kimai timesheets with client-side duplicate detection."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from devecoop_mcp.core.errors import KimaiError, KimaiUnavailableError
from devecoop_mcp.kimai.models import (
    KimaiPendingEntry,
    KimaiPreviewEntry,
    KimaiTimesheetDraft,
    KimaiTimesheetLogResponse,
    KimaiTimesheetPreviewResponse,
    KimaiWrittenEntry,
    kimai_user_summary,
)
from devecoop_mcp.kimai.tokens import create_token, read_token

if TYPE_CHECKING:
    from devecoop_mcp.config import KimaiConfig
    from devecoop_mcp.kimai.client import KimaiClient


MAX_BATCH_ENTRIES = 31
PREVIEW_TTL_SECONDS = 900


class _NormalizedEntry(TypedDict):
    begin: str
    end: str
    duration_minutes: int


def _parse_time(value: str, field: str) -> time:
    """Parse a 24-hour HH:MM value."""
    if len(value) != 5 or value[2] != ":":
        raise ValueError(f"{field} must use 24-hour HH:MM format")
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must use 24-hour HH:MM format") from error


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD value."""
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"date must use YYYY-MM-DD format: {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from error


def _format_hours(minutes: int) -> str:
    """Format a duration in minutes as hours and minutes."""
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} h {remainder} min"
    if hours:
        return f"{hours} h"
    return f"{remainder} min"


def _normalize_description(value: str | None) -> str | None:
    """Strip a description and turn blank values into ``None``."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _local_datetime_string(value: datetime) -> str:
    """Format a naive local datetime for the Kimai API."""
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _same_wall_time(existing: str, expected: str) -> bool:
    """Compare local wall times while ignoring Kimai's UTC offset suffix."""
    return existing[:19] == expected[:19]


def _find_existing_duplicate(
    existing_entries: list[dict[str, Any]],
    begin: str,
    end: str,
    project_id: int,
    activity_id: int,
    description: str | None,
) -> dict[str, Any] | None:
    """Return an exact existing match for the requested entry, if any."""
    normalized_description = _normalize_description(description)
    for entry in existing_entries:
        entry_project = entry.get("project")
        entry_activity = entry.get("activity")
        if not isinstance(entry_project, dict) or not isinstance(entry_activity, dict):
            continue
        if int(entry_project.get("id", -1)) != project_id:
            continue
        if int(entry_activity.get("id", -1)) != activity_id:
            continue
        if not _same_wall_time(str(entry.get("begin", "")), begin):
            continue
        entry_end = entry.get("end")
        if not isinstance(entry_end, str) or not _same_wall_time(entry_end, end):
            continue
        if _normalize_description(entry.get("description")) != normalized_description:
            continue
        return entry
    return None


def _duplicate_message(entry: dict[str, Any], begin: str, end: str) -> str:
    """Build a clear duplicate-entry message with the existing entry ID."""
    return (
        f"An identical Kimai timesheet already exists (id={entry.get('id')}): "
        f"{begin[:10]} from {begin[11:16]} to {end[11:16]}."
    )


def _build_summary(
    user: dict[str, Any],
    project_name: str,
    activity_name: str,
    description: str | None,
    entries: list[_NormalizedEntry],
    total_minutes: int,
) -> str:
    """Build the human-readable confirmation message shown before writing."""
    username = str(user.get("username") or user.get("alias") or user.get("id"))
    lines = [
        f"Usuario: {username}",
        f"Proyecto: {project_name}",
        f"Actividad: {activity_name}",
    ]
    if description is not None:
        lines.append(f"Descripción: {description}")
    lines.append("Entradas:")
    for entry in entries:
        lines.append(
            f"- {entry['begin'][:10]}: {_format_hours(entry['duration_minutes'])} "
            f"({entry['begin'][11:16]}–{entry['end'][11:16]})"  # noqa: RUF001
        )
    lines.append(f"Total: {_format_hours(total_minutes)}")
    return "\n".join(lines)


def _draft_to_normalized(
    draft: KimaiTimesheetDraft,
    default_begin_time: str,
) -> _NormalizedEntry:
    """Validate one draft and normalize it to local datetimes and minutes."""
    parsed_date = _parse_date(draft.date)
    begin_time = _parse_time(draft.begin or default_begin_time, "begin")
    begin_datetime = datetime.combine(parsed_date, begin_time)

    if draft.end is not None:
        if draft.duration_minutes is not None:
            raise ValueError("Provide either end or duration_minutes, not both")
        end_datetime = datetime.combine(parsed_date, _parse_time(draft.end, "end"))
        if end_datetime <= begin_datetime:
            raise ValueError("end must be after begin on the same date")
        duration_minutes = int((end_datetime - begin_datetime).total_seconds() // 60)
    else:
        if draft.duration_minutes is None:
            raise ValueError("Provide end or duration_minutes")
        duration_minutes = draft.duration_minutes
        if not 1 <= duration_minutes <= 1440:
            raise ValueError("duration_minutes must be between 1 and 1440")
        end_datetime = begin_datetime + timedelta(minutes=duration_minutes)
        if end_datetime.date() != parsed_date:
            raise ValueError("duration_minutes must not cross midnight")

    return _NormalizedEntry(
        begin=_local_datetime_string(begin_datetime),
        end=_local_datetime_string(end_datetime),
        duration_minutes=duration_minutes,
    )


def _validate_activity_project(project: dict[str, Any], activity: dict[str, Any]) -> None:
    """Reject an activity that belongs to a different project."""
    activity_project_id = activity.get("project")
    if activity_project_id is None:
        return
    project_id = int(project["id"])
    if int(activity_project_id) == project_id:
        return
    raise ValueError(
        f"Activity {activity.get('name')!r} (id={activity.get('id')}) belongs to project "
        f"id={activity_project_id}, not {project.get('name')!r} (id={project_id})."
    )


def _load_existing(
    client: KimaiClient,
    user_id: int,
    begin_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Return the user's existing entries for a date range."""
    return client.list_timesheets(
        user_id,
        f"{begin_date.isoformat()}T00:00:00",
        f"{end_date.isoformat()}T23:59:59",
        limit=500,
    )


def _token_payload(
    user_id: int,
    project_id: int,
    project_name: str,
    activity_id: int,
    activity_name: str,
    description: str | None,
    entries: list[_NormalizedEntry],
) -> dict[str, Any]:
    """Build the signed payload that authorizes a create batch."""
    return {
        "kind": "create",
        "user_id": user_id,
        "project_id": project_id,
        "project_name": project_name,
        "activity_id": activity_id,
        "activity_name": activity_name,
        "description": description,
        "entries": [{"begin": entry["begin"], "end": entry["end"]} for entry in entries],
    }


def preview_timesheets(
    client: KimaiClient,
    config: KimaiConfig,
    project: str,
    activity: str,
    entries: list[KimaiTimesheetDraft],
    description: str | None = None,
) -> KimaiTimesheetPreviewResponse:
    """Validate a batch, detect duplicates and return a signed confirmation."""
    if not 1 <= len(entries) <= MAX_BATCH_ENTRIES:
        raise ValueError(f"entries must contain between 1 and {MAX_BATCH_ENTRIES} items")

    user = client.resolve_user(config.default_user)
    user_id = int(user["id"])
    project_entity = client.resolve_project(project)
    project_id = int(project_entity["id"])
    project_name = str(project_entity["name"])
    activity_entity = client.resolve_activity(activity)
    activity_id = int(activity_entity["id"])
    activity_name = str(activity_entity["name"])
    _validate_activity_project(project_entity, activity_entity)

    normalized_description = _normalize_description(description)
    normalized_entries = [
        _draft_to_normalized(draft, config.default_begin_time) for draft in entries
    ]

    seen: set[tuple[str, str, int, int, str | None]] = set()
    for entry in normalized_entries:
        key = (
            entry["begin"],
            entry["end"],
            project_id,
            activity_id,
            normalized_description,
        )
        if key in seen:
            raise ValueError(
                f"Duplicate entry within the batch: {entry['begin'][:10]} "
                f"from {entry['begin'][11:16]} to {entry['end'][11:16]}."
            )
        seen.add(key)

    ordered_entries = sorted(normalized_entries, key=lambda entry: entry["begin"])
    begin_date = date.fromisoformat(ordered_entries[0]["begin"][:10])
    end_date = date.fromisoformat(ordered_entries[-1]["end"][:10])
    existing_entries = _load_existing(client, user_id, begin_date, end_date)
    for entry in ordered_entries:
        duplicate = _find_existing_duplicate(
            existing_entries,
            entry["begin"],
            entry["end"],
            project_id,
            activity_id,
            normalized_description,
        )
        if duplicate is not None:
            raise ValueError(_duplicate_message(duplicate, entry["begin"], entry["end"]))

    total_minutes = sum(entry["duration_minutes"] for entry in ordered_entries)
    summary = _build_summary(
        user,
        project_name,
        activity_name,
        normalized_description,
        ordered_entries,
        total_minutes,
    )
    token = create_token(
        _token_payload(
            user_id,
            project_id,
            project_name,
            activity_id,
            activity_name,
            normalized_description,
            ordered_entries,
        ),
        ttl_seconds=PREVIEW_TTL_SECONDS,
    )
    token_payload = read_token(token)

    return KimaiTimesheetPreviewResponse(
        user=kimai_user_summary(user),
        project_id=project_id,
        project_name=project_name,
        activity_id=activity_id,
        activity_name=activity_name,
        description=normalized_description,
        entries=[
            KimaiPreviewEntry(
                date=entry["begin"][:10],
                begin=entry["begin"],
                end=entry["end"],
                duration_minutes=entry["duration_minutes"],
            )
            for entry in ordered_entries
        ],
        total_duration_minutes=total_minutes,
        summary=summary,
        confirmation_token=token,
        expires_at=datetime.fromtimestamp(int(token_payload["exp"]), tz=UTC).isoformat(),
    )


def _read_token_entries(raw_entries: Any) -> list[KimaiPendingEntry]:
    """Validate and map the entry list stored in a preview token."""
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("Invalid preview token. Run the preview again.")
    pending: list[KimaiPendingEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("Invalid preview token. Run the preview again.")
        begin = raw_entry.get("begin")
        end = raw_entry.get("end")
        if not isinstance(begin, str) or not isinstance(end, str):
            raise ValueError("Invalid preview token. Run the preview again.")
        begin_datetime = datetime.fromisoformat(begin)
        end_datetime = datetime.fromisoformat(end)
        pending.append(
            KimaiPendingEntry(
                begin=begin,
                end=end,
                duration_minutes=int((end_datetime - begin_datetime).total_seconds() // 60),
            )
        )
    return pending


def _written_entry(
    payload: dict[str, Any],
    project_name: str,
    activity_name: str,
    description: str | None,
) -> KimaiWrittenEntry:
    """Map a created or recovered Kimai entry to the output model."""
    return KimaiWrittenEntry(
        id=int(payload["id"]),
        begin=str(payload["begin"]),
        end=str(payload["end"]),
        duration_minutes=round(int(payload["duration"]) / 60),
        project_name=project_name,
        activity_name=activity_name,
        description=description,
    )


def _recover_created_entry(
    client: KimaiClient,
    user_id: int,
    entry: KimaiPendingEntry,
    project_id: int,
    activity_id: int,
    description: str | None,
) -> dict[str, Any] | None:
    """Look for an entry that Kimai may have created before timing out."""
    entry_date = datetime.fromisoformat(entry.begin).date()
    try:
        existing_entries = _load_existing(client, user_id, entry_date, entry_date)
    except KimaiError:
        return None
    return _find_existing_duplicate(
        existing_entries,
        entry.begin,
        entry.end,
        project_id,
        activity_id,
        description,
    )


def log_timesheets(
    client: KimaiClient,
    config: KimaiConfig,
    confirmation_token: str,
) -> KimaiTimesheetLogResponse:
    """Write the entries authorized by a preview token, sequentially."""
    payload = read_token(confirmation_token)
    if payload.get("kind") != "create" or payload.get("v") != 1:
        raise ValueError("Unsupported preview token. Run the preview again.")

    user = client.resolve_user(config.default_user)
    user_id = int(user["id"])
    if payload.get("user_id") != user_id:
        raise ValueError("The preview was created for a different user. Run the preview again.")

    project_id = int(payload["project_id"])
    project_name = str(payload["project_name"])
    activity_id = int(payload["activity_id"])
    activity_name = str(payload["activity_name"])
    raw_description = payload.get("description")
    if raw_description is not None and not isinstance(raw_description, str):
        raise ValueError("Invalid preview token. Run the preview again.")
    description = _normalize_description(raw_description)
    pending_entries = _read_token_entries(payload.get("entries"))

    begin_date = min(datetime.fromisoformat(entry.begin).date() for entry in pending_entries)
    end_date = max(datetime.fromisoformat(entry.end).date() for entry in pending_entries)
    existing_entries = _load_existing(client, user_id, begin_date, end_date)
    for entry in pending_entries:
        duplicate = _find_existing_duplicate(
            existing_entries,
            entry.begin,
            entry.end,
            project_id,
            activity_id,
            description,
        )
        if duplicate is not None:
            raise KimaiError(_duplicate_message(duplicate, entry.begin, entry.end))

    written: list[KimaiWrittenEntry] = []
    failed_entry: KimaiPendingEntry | None = None
    pending: list[KimaiPendingEntry] = []
    error_message: str | None = None

    for index, entry in enumerate(pending_entries):
        request_payload: dict[str, Any] = {
            "user": user_id,
            "begin": entry.begin,
            "end": entry.end,
            "project": project_id,
            "activity": activity_id,
        }
        if description is not None:
            request_payload["description"] = description

        try:
            created = client.create_timesheet(request_payload)
        except KimaiUnavailableError:
            recovered = _recover_created_entry(
                client,
                user_id,
                entry,
                project_id,
                activity_id,
                description,
            )
            if recovered is None:
                failed_entry = entry
                pending = pending_entries[index + 1 :]
                error_message = (
                    f"The outcome for the entry on {entry.begin[:10]} from "
                    f"{entry.begin[11:16]} to {entry.end[11:16]} is unknown because "
                    "Kimai did not respond. Check Kimai before retrying."
                )
                break
            written.append(_written_entry(recovered, project_name, activity_name, description))
            continue
        except KimaiError as error:
            failed_entry = entry
            pending = pending_entries[index + 1 :]
            error_message = str(error)
            break

        written.append(_written_entry(created, project_name, activity_name, description))

    status: Literal["ok", "partial", "failed"]
    if failed_entry is None:
        status = "ok"
    elif written:
        status = "partial"
    else:
        status = "failed"

    return KimaiTimesheetLogResponse(
        status=status,
        written=written,
        failed_entry=failed_entry,
        pending=pending,
        error=error_message,
    )
