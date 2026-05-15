"""Tethys master configuration via pydantic-settings.

Cite: pydantic-settings v2 (https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
Trace: parent plan section 6.1 (config / settings discipline)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MasterSettings(BaseSettings):
    """Top-level master settings.

    Loaded from environment variables prefixed ``TETHYS_MASTER_`` and / or
    a ``.env`` file in CWD. CLI flags override.
    """

    model_config = SettingsConfigDict(
        env_prefix="TETHYS_MASTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = Field(default="INFO", description="structlog log level")
    log_format: str = Field(default="plain", description="'plain' or 'json'")
    profile: str = Field(default="marine", description="'marine' or 'space'")

    udp_default_host: str = Field(default="127.0.0.1")
    udp_default_port: int = Field(default=5555, ge=1, le=65535)

    connect_timeout_ms: int = Field(default=1000, ge=10, le=60000)
    response_timeout_ms: int = Field(default=500, ge=10, le=10000)
