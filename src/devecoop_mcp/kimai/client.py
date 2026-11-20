"""HTTP client for the Kimai API.

The client only depends on the Python standard library for HTTP. A transport
callable can be injected in tests so no real request leaves the process.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, cast

from devecoop_mcp.config import KimaiConfig
from devecoop_mcp.core.errors import KimaiError, KimaiUnavailableError

Transport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _default_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    """Send a request with ``urllib`` and normalize network failures."""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise KimaiUnavailableError(
            f"Could not reach the Kimai API at {request.full_url}: {error}"
        ) from error


def _parse_error_details(body: bytes) -> object | None:
    """Parse an error response body, falling back to decoded text."""
    if not body:
        return None
    try:
        return cast(object, json.loads(body))
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="replace")


class KimaiClient:
    """Minimal Kimai API client for the endpoints used by the tools."""

    def __init__(
        self,
        config: KimaiConfig,
        transport: Transport | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._config = config
        self._transport = transport if transport is not None else _default_transport
        self._timeout = timeout

    def get_version(self) -> dict[str, Any]:
        """Return the Kimai release information."""
        return cast(dict[str, Any], self._request("GET", "/version"))

    def get_current_user(self) -> dict[str, Any]:
        """Return the user authenticated by the configured API credentials."""
        return cast(dict[str, Any], self._request("GET", "/users/me"))

    def get_timesheet_config(self) -> dict[str, Any]:
        """Return the instance-wide timesheet configuration."""
        return cast(dict[str, Any], self._request("GET", "/config/timesheet"))

    def list_users(self, term: str) -> list[dict[str, Any]]:
        """Return visible users matching ``term``."""
        return cast(
            list[dict[str, Any]],
            self._request("GET", "/users", params={"visible": 1, "term": term}),
        )

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Return a single user entity by numeric ID."""
        return cast(dict[str, Any], self._request("GET", f"/users/{user_id}"))

    def resolve_user(self, value: str) -> dict[str, Any]:
        """Resolve a username, alias or numeric ID to a Kimai user entity.

        Raises:
            KimaiError: If no user matches or the value is ambiguous.
        """
        if value.isdigit():
            return self.get_user(int(value))

        normalized = value.casefold()
        matches = [
            user
            for user in self.list_users(value)
            if str(user.get("username", "")).casefold() == normalized
            or str(user.get("alias") or "").casefold() == normalized
        ]
        if not matches:
            raise KimaiError(
                f"No Kimai user matches {value!r}. Use a numeric user ID or check the username."
            )
        if len(matches) > 1:
            usernames = ", ".join(str(user.get("username", "")) for user in matches)
            raise KimaiError(
                f"Multiple Kimai users match {value!r}: {usernames}. Use a numeric user ID instead."
            )
        return matches[0]

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str | int] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Send an API request and return the parsed JSON body."""
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self._config.base_url}/api{path}{query}"
        headers = {
            "X-AUTH-USER": self._config.api_user,
            "X-AUTH-TOKEN": self._config.api_token.get_secret_value(),
            "Accept": "application/json",
        }

        data: bytes | None = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        status, body = self._transport(request, self._timeout)

        if status >= 400:
            details = _parse_error_details(body)
            message = f"Kimai API request failed with status {status}"
            if isinstance(details, dict):
                api_message = details.get("message")
                if isinstance(api_message, str) and api_message:
                    message = f"{message}: {api_message}"
            raise KimaiError(message, status_code=status, details=details)

        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise KimaiError("Kimai API returned invalid JSON.") from error
