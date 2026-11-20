"""Shared error types for the Devecoop MCP server."""

from __future__ import annotations


class DevecoopError(Exception):
    """Base class for all Devecoop MCP errors."""


class ConfigurationError(DevecoopError):
    """Raised when required configuration is missing or invalid."""


class IndexNotFoundError(DevecoopError):
    """Raised when the wiki index has not been built yet."""


class WikiNotFoundError(DevecoopError):
    """Raised when the wiki clone or a requested page is missing."""


class PathTraversalError(DevecoopError):
    """Raised when a requested page path escapes the wiki root."""


class KimaiError(DevecoopError):
    """Raised when the Kimai API returns an error or an invalid response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class KimaiUnavailableError(KimaiError):
    """Raised when Kimai cannot be reached due to a network or timeout failure."""
