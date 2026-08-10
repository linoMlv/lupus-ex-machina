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
from lupus_ex_machina.hosting.broadcast import Heard, Told
from lupus_ex_machina.hosting.protocol import NOTHING_HEARD, SHOWN, Broadcast, RateLimited

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
    confirming = asyncio.ensure_future(_take_confirmations(websocket, game, progress))
    try:
        await asyncio.wait({catching_up, confirming}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (catching_up, confirming):
            task.cancel()


class Progress:
    """What a client has been sent, in the two counts that matter.

    A client can only ever confirm a sequence **it has seen**, and a player sees
    a fraction of the journal: a wolf's night never reaches them, so they can
    never name it. The pacing, on the other hand, counts in facts *recorded*.
    Confirming one in terms of the other would stall a played game for ever —
    which is exactly what it did before this existed.

    So the server keeps both: how far down the journal it has read, and the last
    sequence it actually put on the wire. A client that names the second has
    caught up with the first.
    """

    def __init__(self) -> None:
        """Start with nothing read, nothing sent and nothing confirmed."""
        self.read = NOTHING_HEARD
        self.wired = NOTHING_HEARD
        self.confirmed = NOTHING_HEARD

    @property
    def caught_up(self) -> bool:
        """Whether the client has named everything that was put on the wire.

        Facts it was never entitled to see do not count against it: a night of
        the pack is nothing a villager can confirm, and holding a game until
        they did would hold it for ever.
        """
        return self.confirmed >= self.wired


async def _keep_up(
    websocket: WebSocket, game: HostedGame, heard: Heard, progress: Progress, *, since: int
) -> None:
    """Send the backlog, then every fact as it comes, until the game is over."""
    await _send(websocket, tuple(game.events), game, progress, after=since)
    with suppress(WebSocketDisconnect, asyncio.CancelledError):
        while (told := await heard.get()) is not None:
            await _relay(websocket, told, game, progress)
        await websocket.close(reason="La partie est terminée.")


async def _relay(websocket: WebSocket, told: Told, game: HostedGame, progress: Progress) -> None:
    """Pass on what the game had to say, whichever of the two things it was.

    A wait is not a fact: it says nothing about the game, only about the
    provider playing it, so it carries no sequence and moves nothing along
    (D-066). It goes out as it is, to whoever is watching.
    """
    if isinstance(told, RateLimited):
        await websocket.send_json(Broadcast(waiting=told.seconds).model_dump(mode="json"))
        return
    await _send(websocket, (told,), game, progress, after=progress.read)


async def _take_confirmations(websocket: WebSocket, game: HostedGame, progress: Progress) -> None:
    """Take what the client says it has shown, which is what lets the game go on.

    A client that says nothing is a client nobody is watching with: the game
    plays its few turns of lead and waits, which is the whole point (D-023).
    Anything that is not a confirmation is ignored rather than fatal — the
    stream is one-way in spirit, and a stray message must not end a game.

    A client that has named the last thing it was sent has caught up with
    everything read to produce it, whether or not it was allowed to see all of
    it — see :class:`Progress`.
    """
    with suppress(WebSocketDisconnect, asyncio.CancelledError):
        while True:
            said = await websocket.receive_json()
            shown = said.get(SHOWN) if isinstance(said, dict) else None
            if isinstance(shown, int):
                progress.confirmed = max(progress.confirmed, shown)
                _let_the_game_go_on(game, progress)


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
    theirs = project_journal(fresh, recipient_for(game.state))
    if theirs:
        await websocket.send_json(Broadcast(events=theirs).model_dump(mode="json"))
        progress.wired = theirs[-1].sequence
    progress.read = max((event.sequence for event in fresh), default=after)
    _let_the_game_go_on(game, progress)


def _let_the_game_go_on(game: HostedGame, progress: Progress) -> None:
    """Tell the game how far this client has kept up, when it has.

    Called from both sides on purpose. A confirmation is the obvious one; the
    other is a fact the client was not entitled to, which leaves it up to date
    without it having said a word.
    """
    if progress.caught_up:
        game.shown(progress.read)
