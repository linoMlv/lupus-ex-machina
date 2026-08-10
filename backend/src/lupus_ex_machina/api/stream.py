"""Following a game in real time, projected before a byte of it leaves (J8.3).

Three things hold this together, and each is a decision rather than a detail.

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
"""

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lupus_ex_machina.api.auth import is_authenticated
from lupus_ex_machina.api.session import SESSION_COOKIE
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.hosting import GameHost, HostedGame
from lupus_ex_machina.hosting.audience import recipient_for
from lupus_ex_machina.hosting.broadcast import Heard
from lupus_ex_machina.hosting.protocol import NOTHING_HEARD, Broadcast

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
    """
    sent = await _send(websocket, tuple(game.events), game, after=since)
    with suppress(WebSocketDisconnect, asyncio.CancelledError):
        while (event := await heard.get()) is not None:
            sent = await _send(websocket, (event,), game, after=sent)
        await websocket.close(reason="La partie est terminée.")


async def _send(
    websocket: WebSocket, events: tuple[Event, ...] | tuple[()], game: HostedGame, *, after: int
) -> int:
    """Send whatever of those facts follows ``after`` and is theirs to see.

    Returns how far the client has now been taken, which is what makes a fact
    heard twice cost nothing.
    """
    fresh = tuple(event for event in events if event.sequence > after)
    theirs = project_journal(fresh, recipient_for(game.state))
    if theirs:
        await websocket.send_json(Broadcast(events=theirs).model_dump(mode="json"))
    return max((event.sequence for event in fresh), default=after)
