"""Application configuration loaded from environment variables and ``.env``."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from devecoop_mcp.core.errors import ConfigurationError

DEFAULT_INDEX_PATH = Path(".cache/wiki_index.sqlite3")


class Settings(BaseSettings):
    """Runtime configuration for the Devecoop MCP server.

    ``WIKI_PATH`` is required at runtime, but the field stays optional so that
    metadata commands such as ``devecoop-mcp --help`` and ``--version`` work
    without any configuration. Call :meth:`require_wiki_path` before using the
    wiki feature.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    wiki_path: Path | None = Field(
        default=None,
        description="Absolute path to the local clone of the Devecoop wiki.",
    )
    wiki_index_path: Path = Field(
        default=DEFAULT_INDEX_PATH,
        description="Path to the SQLite FTS5 index.",
    )
    wiki_base_url: str | None = Field(
        default=None,
        description="Optional GitLab base URL override for citation links.",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level for stderr logging.",
    )

    @field_validator("wiki_path", "wiki_base_url", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        """Treat empty environment values as unset."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def require_wiki_path(self) -> Path:
        """Return the configured wiki path.

        Raises:
            ConfigurationError: If ``WIKI_PATH`` is not set.
        """
        if self.wiki_path is None:
            raise ConfigurationError(
                "Missing required environment variable WIKI_PATH. "
                "Set it to the absolute path of your local wiki clone "
                "(see .env.example)."
            )
        return self.wiki_path.expanduser().resolve()
