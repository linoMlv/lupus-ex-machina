"""Runtime configuration.

Every value is read from the environment with the ``LUPUS_`` prefix, so the
image never embeds a setting and the platform can override any of them.

The default paths are resolved relative to the repository, which is what a
developer running ``make run`` from a checkout needs. A deployed container does
not have that layout: the Dockerfile sets ``LUPUS_FRONTEND_DIST`` and
``LUPUS_MODELS_DIR`` explicitly. See docs/DEPLOY.md.
"""

import secrets
from pathlib import Path
from typing import Literal

from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

LogLevel = Literal["critical", "error", "warning", "info", "debug", "trace"]


class Settings(BaseSettings):
    """Settings of a running instance."""

    model_config = SettingsConfigDict(
        env_prefix="LUPUS_",
        # The repository root first, then the working directory. Commands run
        # from `backend/` (that is where the project lives) while the `.env`
        # sits beside `.env.example` at the root, so looking only where the
        # process happens to start would find nothing.
        env_file=(REPOSITORY_ROOT / ".env", ".env"),
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
    llm_api_key: str | None = Field(
        default=None,
        description="Key of the OpenAI-compatible provider. Without it, no game with models.",
    )
    """Never in the image, never in the repository: it is read from the
    environment like everything else, and a game without it fails loudly rather
    than silently playing itself (D-090)."""

    llm_base_url: str = Field(
        default="https://api.mistral.ai/v1",
        description="Endpoint of the OpenAI-compatible provider.",
    )
    password: str | None = Field(
        default=None,
        description="Password the private application is behind. Without it, nobody gets in.",
    )
    """In the clear, on purpose (D-098). A hash protects a table of passwords
    against being stolen; here there is one secret, one user, and whoever runs
    the server already holds it in the clear — hashing would move the secret
    without protecting it, against one more dependency. Absent, the door stays
    shut: forgetting to set a password must never be what opens it."""

    secret_key: str | None = Field(
        default=None,
        description="Secret the session cookie is signed with, and provider keys are kept under.",
    )
    """**Optional here, and read two different ways** — which is the whole reason
    it is no longer drawn in this field.

    The cookie does without it (D-098): :attr:`session_key` draws one at
    start-up, which logs everyone out on a restart and costs nothing. A key
    nobody chose beats a known one, and a private application restarts rarely.

    The provider registry cannot do the same (D-113). Keys encrypted under a
    drawn secret would be **unreadable** at the next restart, so registering one
    without a supplied secret is refused rather than half-done. Telling the two
    apart is what this field being ``None`` says."""

    _drawn_key: str = PrivateAttr(default_factory=lambda: secrets.token_hex(32))
    """The stand-in for an unsupplied secret. Drawn once per process, so a
    session outlives a request without outliving a restart."""

    @property
    def session_key(self) -> str:
        """What the session cookie is signed with, supplied or drawn (D-098)."""
        return self.secret_key if self.secret_key is not None else self._drawn_key
