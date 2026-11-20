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
