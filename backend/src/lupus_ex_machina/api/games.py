"""Creating, starting, reading and giving up the game (J8.2).

Two gestures rather than one (D-103): `POST /api/game` deals the table, and
`POST /api/game/start` is what sets it playing. A game that started itself would
spend the call budget of a table nobody has come to watch yet.

**What comes back here holds nothing that needs projecting.** Who sits where and
who is alive are public — death always is (D-072) — while what anybody was dealt
is the whole of the game. The journal, which does need projecting, is served by
its own route and filtered before it leaves (D-046).

Messages are French because they reach a screen (HR-6).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from lupus_ex_machina.api.auth import require_session
from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.rules import GameMode
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.hosting import (
    AlreadyStartedError,
    GameHost,
    HostedGame,
    OneGameAtATimeError,
    Stage,
)

router = APIRouter(
    prefix="/api/game",
    tags=["game"],
    dependencies=[Depends(require_session)],
)

NO_PROVIDER = "Aucun modèle configuré : renseignez LUPUS_LLM_API_KEY pour pouvoir jouer une partie."


class SeatSummary(BaseModel):
    """A seat at the table, as everybody may see it."""

    seat: int
    name: str
    alive: bool


class GameSummary(BaseModel):
    """A game, as everybody may see it."""

    stage: Stage
    mode: GameMode
    day: int
    outcome: Outcome | None = None
    players: list[SeatSummary] = Field(default_factory=list)


def summarised(game: HostedGame) -> GameSummary:
    """What a game says about itself, holding nothing anybody has to be shielded from."""
    state = game.state
    return GameSummary(
        stage=game.stage,
        mode=game.configuration.rules.table.mode,
        day=state.day,
        outcome=game.outcome,
        players=[
            SeatSummary(seat=player.seat, name=player.name, alive=state.player(player.id).alive)
            for player in game.players
        ],
    )


def host_of(request: Request) -> GameHost:
    """The host of the running application, or a plain refusal to play at all."""
    host: GameHost | None = request.app.state.host
    if host is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NO_PROVIDER)
    return host


def game_of(request: Request) -> HostedGame:
    """The game being hosted, or a plain refusal."""
    hosted = host_of(request).current
    if hosted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune partie en cours.")
    return hosted


Hosted = Annotated[HostedGame, Depends(game_of)]
Host = Annotated[GameHost, Depends(host_of)]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Deal a game")
async def create(configuration: GameConfiguration, host: Host) -> GameSummary:
    """Deal a table from that configuration. Nothing is played until it starts."""
    try:
        return summarised(host.create(configuration))
    except OneGameAtATimeError as taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(taken)) from taken


@router.get("", summary="Read the game being hosted")
async def read(game: Hosted) -> GameSummary:
    """Say where the game stands, in what everybody is entitled to know."""
    return summarised(game)


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, summary="Set the game playing")
async def start(game: Hosted) -> GameSummary:
    """Set the game playing. It runs on its own from here (D-103)."""
    try:
        game.start()
    except AlreadyStartedError as already:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(already)) from already
    return summarised(game)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Give the game up")
async def abandon(request: Request) -> None:
    """Give up the game, freeing the place at once (D-101)."""
    game_of(request)
    await host_of(request).abandon()
