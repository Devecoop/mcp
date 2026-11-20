"""Application configuration loaded from environment variables and ``.env``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from devecoop_mcp.core.errors import ConfigurationError

DEFAULT_INDEX_PATH = Path(".cache/wiki_index.sqlite3")
DEFAULT_KIMAI_BEGIN_TIME = "09:00"
_BEGIN_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class KimaiConfig:
    """Validated Kimai connection settings."""

    base_url: str
    api_user: str
    api_token: SecretStr
    default_user: str
    default_begin_time: str


class Settings(BaseSettings):
    """Runtime configuration for the Devecoop MCP server.

    Features are optional and enabled by their own environment variables:
    ``WIKI_PATH`` enables the wiki oracle, and the ``KIMAI_*`` variables enable
    the Kimai integration. Metadata commands such as ``devecoop-mcp --help``
    and ``--version`` work without any configuration.
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
    kimai_url: str | None = Field(
        default=None,
        description="Base URL of the Kimai instance, without the /api suffix.",
    )
    kimai_api_user: str | None = Field(
        default=None,
        description="Kimai API user sent in the X-AUTH-USER header.",
    )
    kimai_api_token: SecretStr | None = Field(
        default=None,
        description="Kimai API token sent in the X-AUTH-TOKEN header.",
    )
    kimai_default_user: str | None = Field(
        default=None,
        description="Default Kimai user username or numeric ID used as the target user.",
    )
    kimai_default_begin_time: str = Field(
        default=DEFAULT_KIMAI_BEGIN_TIME,
        description="Default begin time for new timesheets in 24-hour HH:MM format.",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level for stderr logging.",
    )

    @field_validator(
        "wiki_path",
        "wiki_base_url",
        "kimai_url",
        "kimai_api_user",
        "kimai_api_token",
        "kimai_default_user",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        """Treat empty environment values as unset."""
        if isinstance(value, SecretStr):
            return None if not value.get_secret_value().strip() else value
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("kimai_url", mode="after")
    @classmethod
    def _normalize_kimai_url(cls, value: str | None) -> str | None:
        """Normalize the Kimai base URL and validate its scheme."""
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if normalized.endswith("/api"):
            normalized = normalized[: -len("/api")].rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("KIMAI_URL must start with http:// or https://")
        return normalized

    @field_validator("kimai_default_begin_time")
    @classmethod
    def _validate_default_begin_time(cls, value: str) -> str:
        """Require a valid 24-hour HH:MM time."""
        if _BEGIN_TIME_PATTERN.fullmatch(value) is None:
            raise ValueError("KIMAI_DEFAULT_BEGIN_TIME must use 24-hour HH:MM format")
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

    def kimai_config(self) -> KimaiConfig | None:
        """Return the Kimai configuration, validating its required variables.

        Returns:
            The Kimai configuration, or ``None`` when the four required Kimai
            variables are all unset.

        Raises:
            ConfigurationError: If the Kimai configuration is incomplete.
        """
        kimai_url = self.kimai_url
        api_user = self.kimai_api_user
        api_token = self.kimai_api_token
        default_user = self.kimai_default_user

        if (
            kimai_url is not None
            and api_user is not None
            and api_token is not None
            and default_user is not None
        ):
            return KimaiConfig(
                base_url=kimai_url,
                api_user=api_user,
                api_token=api_token,
                default_user=default_user,
                default_begin_time=self.kimai_default_begin_time,
            )

        missing = [
            name
            for name, value in (
                ("KIMAI_URL", kimai_url),
                ("KIMAI_API_USER", api_user),
                ("KIMAI_API_TOKEN", api_token),
                ("KIMAI_DEFAULT_USER", default_user),
            )
            if value is None
        ]
        if len(missing) == 4:
            return None
        raise ConfigurationError(
            "Incomplete Kimai configuration. Missing environment variables: " + ", ".join(missing)
        )
