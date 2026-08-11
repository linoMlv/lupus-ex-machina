"""Following a game in real time, projected before a byte of it leaves (J8.3).

Four things hold this together, and each is a decision rather than a detail.

**The websocket authenticates itself.** It carries the whole of what a game
produces, so borrowing the protection of the HTTP routes would leave the traffic
that matters wide open (J8.1.2).

**A client says where it got to, and is sent what follows.** One path for a first
connection and a reconnection alike (D-102), which is what leaves no gap between
reading a history and subscribing to what comes next — the listener is attached
*before* the backlog is read, and anything heard twice is dropped by its
sequence.

**Everything is projected, and the recipient comes from the game.** Never from
the client: a spectator is omniscient, so a mode chosen per connection would let
anybody open a second tab on a game they are playing (D-100).

**It carries the dialogue of a turn, and nothing else upward** (D-109, J8.5).
The question the game puts to its player, and the answer to it. The buttons and
the moderator's hand are routes, because they outlive a connection.
"""

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lupus_ex_machina.api.auth import is_authenticated
from lupus_ex_machina.api.incoming import take_what_the_client_says
from lupus_ex_machina.api.progress import Progress, let_the_game_go_on
from lupus_ex_machina.api.session import SESSION_COOKIE
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.recollection import recollected
from lupus_ex_machina.hosting import GameHost, HostedGame
from lupus_ex_machina.hosting.audience import recipient_for
from lupus_ex_machina.hosting.broadcast import Heard, Told
from lupus_ex_machina.hosting.protocol import (
    NOTHING_HEARD,
    Broadcast,
    QuestionClosed,
    QuestionPut,
    RateLimited,
)

router = APIRouter(tags=["game"])

#: Closing codes, as the websocket protocol words them.
POLICY_VIOLATION = 1008


@router.websocket("/api/game/stream")
async def stream(websocket: WebSocket, since: int = NOTHING_HEARD) -> None:
    """Send the game as it happens, to whoever is entitled to see it."""
    settings = websocket.app.state.settings
    if not is_authenticated(websocket.cookies.get(SESSION_COOKIE), settings):
        await websocket.close(code=POLICY_VIOLATION, reason="Session absente ou expirée.")
        return

    host: GameHost | None = websocket.app.state.host
    game = host.current if host is not None else None
    if game is None:
        await websocket.close(code=POLICY_VIOLATION, reason="Aucune partie en cours.")
        return

    await websocket.accept()
    with game.listening() as heard:
        await _follow(websocket, game, heard, since=since)


async def _follow(websocket: WebSocket, game: HostedGame, heard: Heard, *, since: int) -> None:
    """Catch the client up, then keep it up, until the game or the client ends it.

    The backlog is read *after* the listener is attached, so a fact recorded
    between the two is heard rather than missed; it then arrives twice, and the
    sequence is what drops the copy.

    Sending and listening run side by side, because a client that only spoke
    when spoken to could never say it had caught up — and the game waits on
    exactly that (J8.4). Whichever ends first ends the connection: a client that
    hangs up stops the sending, and a game that ends stops the listening.
    """
    progress = Progress()
    catching_up = asyncio.ensure_future(_keep_up(websocket, game, heard, progress, since=since))
    listening = asyncio.ensure_future(take_what_the_client_says(websocket, game, progress))
    try:
        await asyncio.wait({catching_up, listening}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (catching_up, listening):
            task.cancel()


async def _keep_up(
    websocket: WebSocket, game: HostedGame, heard: Heard, progress: Progress, *, since: int
) -> None:
    """Send the backlog, then every fact as it comes, until the game is over."""
    await _send(websocket, tuple(game.events), game, progress, after=since)
    await _say_what_is_being_waited_on(websocket, game)
    with suppress(WebSocketDisconnect, asyncio.CancelledError):
        while (told := await heard.get()) is not None:
            await _relay(websocket, told, game, progress)
        await websocket.close(reason="La partie est terminée.")


async def _say_what_is_being_waited_on(websocket: WebSocket, game: HostedGame) -> None:
    """Tell a client that has just arrived what the game is waiting on it for.

    A question put before this client existed was announced to nobody, so a
    person who refreshed their browser would otherwise sit in front of a game
    that is waiting on them and says nothing — the same gap between a history
    and a subscription that D-102 closes for the facts.

    A question put between the listener being attached and this line arrives
    twice. Harmless, and cheaper than ordering the two: a question carries its
    number, so the second is the same question said again.
    """
    standing = game.person.question if game.person is not None else None
    if standing is not None:
        await _say(websocket, Broadcast(question=standing))


async def _relay(websocket: WebSocket, told: Told, game: HostedGame, progress: Progress) -> None:
    """Pass on what the game had to say, whichever of the three things it was.

    A wait is not a fact: it says nothing about the game, only about the
    provider playing it, so it carries no sequence and moves nothing along
    (D-066). Neither is a question — that says what the game is waiting on its
    player for (D-096). Both go out as they are, to whoever is watching.
    """
    if isinstance(told, RateLimited):
        await _say(websocket, Broadcast(waiting=told.seconds))
        return
    if isinstance(told, QuestionPut | QuestionClosed):
        await _say(websocket, Broadcast(question=told))
        return
    await _send(websocket, (told,), game, progress, after=progress.read)


async def _send(
    websocket: WebSocket,
    events: tuple[Event, ...] | tuple[()],
    game: HostedGame,
    progress: Progress,
    *,
    after: int,
) -> None:
    """Send whatever of those facts follows ``after`` and is theirs to see.

    Both counts of :class:`Progress` move here, and only here: how far the
    journal was read, and the last sequence that went out.
    """
    fresh = tuple(event for event in events if event.sequence > after)
    theirs = _for(game, project_journal(fresh, recipient_for(game.state)))
    if theirs:
        await _say(websocket, Broadcast(events=theirs))
        progress.wired = theirs[-1].sequence
    progress.read = max((event.sequence for event in fresh), default=after)
    let_the_game_go_on(game, progress)


def _for(game: HostedGame, projected: tuple[Event, ...]) -> tuple[Event, ...]:
    """The same facts, minus what this recipient may no longer look up (D-111).

    The same rule the engine applies to what it hands an agent, applied to the
    one player who has a screen: without it, the option would bind models alone
    and the screen would become a systematic advantage (D-017).

    **The spectator is left whole**, and so is a player whose character has died
    under D-105 — ``recipient_for`` already answers the spectator for both. They
    watch a game they are not in, and D-111 governs what somebody still *playing*
    may re-read.

    One filter, two behaviours, without a case for either: a count travelling on
    the day it is read out is of the day in progress and stays, while the same
    fact replayed to a client catching up is old and goes.
    """
    if recipient_for(game.state).is_spectator:
        return projected
    return recollected(projected, day=game.state.day, information=game.state.rules.information)


async def _say(websocket: WebSocket, broadcast: Broadcast) -> None:
    """Put one envelope on the wire. The single place anything leaves this server."""
    await websocket.send_json(broadcast.model_dump(mode="json"))
