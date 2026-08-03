"""Runtime configuration.

Every value is read from the environment with the ``LUPUS_`` prefix, so the
image never embeds a setting and the platform can override any of them.

The default paths are resolved relative to the repository, which is what a
developer running ``make run`` from a checkout needs. A deployed container does
not have that layout: the Dockerfile sets ``LUPUS_FRONTEND_DIST`` and
``LUPUS_MODELS_DIR`` explicitly. See docs/DEPLOY.md.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

LogLevel = Literal["critical", "error", "warning", "info", "debug", "trace"]


class Settings(BaseSettings):
    """Settings of a running instance."""

    model_config = SettingsConfigDict(
        env_prefix="LUPUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(
        default="127.0.0.1",
        description="Interface the server binds to. Containers must use 0.0.0.0.",
    )
    port: int = Field(default=8000, ge=1, le=65535, description="TCP port the server listens on.")
    log_level: LogLevel = Field(default="info", description="Verbosity of the server logs.")
    frontend_dist: Path = Field(
        default=REPOSITORY_ROOT / "frontend" / "dist",
        description="Directory holding the built front end. Serving is skipped when missing.",
    )
    models_dir: Path = Field(
        default=REPOSITORY_ROOT / "assets",
        description="Directory holding the GLB models exposed under /models.",
    )
