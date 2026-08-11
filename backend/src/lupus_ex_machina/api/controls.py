"""The hands that reach into a running game from outside its rules (J8.5, D-109).

Routes rather than websocket messages, and that is a decision rather than a
convenience. They outlive a connection, and the moderator's hand works **in both
modes** (D-048) — so in one where a client never sends anything upward at all.
The websocket carries the dialogue of a turn: the question, and its answer.

The controls themselves live on the game (`hosting/hands.py`), read between
turns by the engine. Nothing here decides anything; it says who is allowed to
touch what, and turns a refusal into a status.

Messages are French because they reach a screen (HR-6).
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.api.auth import require_session
from lupus_ex_machina.api.games import Hosted
from lupus_ex_machina.hosting.errors import NobodyIsPlayingError

router = APIRouter(
    prefix="/api/game",
    tags=["game"],
    dependencies=[Depends(require_session)],
)


class DebateCall(BaseModel):
    """What the moderator allows the debate from here on (D-048)."""

    model_config = ConfigDict(frozen=True)

    turns: int = Field(
        ge=0,
        description="Tours de parole encore permis avant le vote. Zéro appelle le vote aussitôt.",
    )
    """Never below nought: zero already means "vote now", and there is nothing
    a negative allowance could ask for that zero does not."""


class DebateAllowance(BaseModel):
    """How much longer the debate may run."""

    model_config = ConfigDict(frozen=True)

    turns_left: int | None


@router.post(
    "/floor/request",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ask for the floor",
)
async def request_the_floor(game: Hosted) -> None:
    """Enter the person in the next auction, to be weighed like anybody else (D-107)."""
    _for_the_person(lambda: game.hands.request_the_floor())


@router.post(
    "/floor/claim",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Take the floor outright",
)
async def claim_the_floor(game: Hosted) -> None:
    """Hand the person the next turn at the floor, without an auction (D-014).

    Read between turns, so the turn under way is played to its end first — and
    a game somebody is playing runs a single turn ahead of them, which is what
    makes there never be a turn to throw away (J8.4).
    """
    _for_the_person(lambda: game.hands.claim_the_floor())


@router.post(
    "/debate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Say how much longer the debate may run",
)
async def call_the_debate(called: DebateCall, game: Hosted) -> DebateAllowance:
    """Allow the debate that many more turns. Zero calls the vote at once (D-048)."""
    game.hands.cut_the_debate_to(called.turns)
    return DebateAllowance(turns_left=game.hands.debate_turns_left)


def _for_the_person(press: Callable[[], None]) -> None:
    """Work a button that only exists when somebody sits at the table.

    A watched game is refused out loud rather than answered with nothing: a
    button that replies and does nothing is the hardest kind of fault to see
    from a screen.
    """
    try:
        press()
    except NobodyIsPlayingError as nobody:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(nobody)) from nobody
