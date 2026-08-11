"""Getting in, and being kept out (J8.1, D-045, D-098).

One password, one cookie, one user. What is worth saying about the shape:

* **A password nobody set opens nothing.** The check is not "is this the
  password" but "is there one, and is this it" — an application deployed before
  its environment was filled in has to be shut, not open.
* **Both comparisons are constant time.** The password because it is a secret,
  the signature because it stands for one.
* **The websocket cannot borrow the protection of the routes.** It carries the
  whole of the information a game produces, so it checks the same cookie itself
  — which is why the check lives in a function rather than in a dependency
  alone.

Messages are French because they reach a screen; everything around them is
English (HR-6).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from lupus_ex_machina.api.session import (
    SESSION_COOKIE,
    SESSION_LIFETIME,
    minted,
    valid,
)
from lupus_ex_machina.config import Settings
from lupus_ex_machina.engine.journal import utc_now

router = APIRouter(prefix="/api", tags=["session"])

ENCODING = "utf-8"


class Credentials(BaseModel):
    """What is offered at the door."""

    password: str = Field(description="Mot de passe de l'application.")


class SessionState(BaseModel):
    """What an open session says about itself."""

    open: bool = True


def opens_the_door(password: str, settings: Settings) -> bool:
    """Whether that password is the one this application is behind.

    Compared in constant time, and refused outright when none is configured:
    without the first test, an empty password would match an empty setting.
    """
    if settings.password is None:
        return False
    return secrets.compare_digest(password.encode(ENCODING), settings.password.encode(ENCODING))


def is_authenticated(token: str | None, settings: Settings) -> bool:
    """Whether that cookie is a session this application signed.

    Takes the raw cookie so the websocket can ask the same question the routes
    do: authenticating the HTTP routes protects none of the traffic that matters.
    """
    if token is None:
        return False
    return valid(token, settings.session_key, at=utc_now())


def settings_of(request: Request) -> Settings:
    """The settings the running application was built with."""
    configured: Settings = request.app.state.settings
    return configured


def require_session(
    request: Request,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    """Refuse anyone without a valid session. Declared by every guarded route."""
    if not is_authenticated(session, settings_of(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session absente ou expirée.",
        )


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT, summary="Open a session")
async def open_session(credentials: Credentials, request: Request, response: Response) -> None:
    """Take the password and hand back the cookie that stands for it."""
    settings = settings_of(request)
    if not opens_the_door(credentials.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect.",
        )

    response.set_cookie(
        SESSION_COOKIE,
        minted(settings.session_key, at=utc_now()),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="strict",
    )


@router.get(
    "/session",
    summary="Report whether the session is open",
    dependencies=[Depends(require_session)],
)
async def read_session() -> SessionState:
    """Say that the session is open. Reaching this at all is the answer."""
    return SessionState()


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT, summary="Give up the session")
async def close_session(response: Response) -> None:
    """Drop the cookie. Nothing is stored, so there is nothing else to forget."""
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="strict")
