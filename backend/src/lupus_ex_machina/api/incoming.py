"""What a client sends up the stream, and what is done with it (J8.5.6).

Two things only, and the shortness of that list is the design. **How far it has
displayed**, which is what lets the game go on (D-023). And **the answer to a
question the game put to its player** (D-096). The buttons and the moderator's
hand are routes: they outlive a connection, and one of them works in a mode with
no upward channel at all (D-109).

Anything else is ignored rather than fatal. The stream is one-way in spirit, and
a stray message must not end somebody's game.

**A malformed answer is ignored too, and the question stays standing.** That is
what makes it safe: the client has only to send again. Refusing loudly instead
would need a second protocol for saying so, and would still leave the same
question waiting.
"""

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from lupus_ex_machina.api.progress import Progress, let_the_game_go_on
from lupus_ex_machina.engine.turn import Reflection, Turn
from lupus_ex_machina.hosting import HostedGame
from lupus_ex_machina.hosting.protocol import ANSWER, SHOWN, Answer, AskedFor


async def take_what_the_client_says(
    websocket: WebSocket, game: HostedGame, progress: Progress
) -> None:
    """Read the client for as long as it talks, acting on what it says.

    A client that says nothing is a client nobody is watching with: the game
    plays its few turns of lead and waits, which is the whole point (D-023).
    """
    with suppress(WebSocketDisconnect, asyncio.CancelledError):
        while True:
            said = await websocket.receive_json()
            if not isinstance(said, dict):
                continue
            _take_what_was_shown(game, progress, said.get(SHOWN))
            _take_what_was_answered(game, said.get(ANSWER))


def _take_what_was_shown(game: HostedGame, progress: Progress, shown: object) -> None:
    """Take how far the client has displayed, which is what unblocks the game.

    A client that has named the last thing it was sent has caught up with
    everything read to produce it, whether or not it was allowed to see all of
    it — see :class:`Progress`.
    """
    if isinstance(shown, int):
        progress.confirmed = max(progress.confirmed, shown)
        let_the_game_go_on(game, progress)


def _take_what_was_answered(game: HostedGame, said: object) -> None:
    """Hand the person's answer to the seat that is waiting on it (D-096).

    The **question decides the shape** the answer is read as, because the
    question is the server's own. Read as whatever the client sent, a turn
    offered where a stock-taking was asked for would be taken with its move
    silently dropped — a turn being a stock-taking with a move on it.
    """
    person = game.person
    if person is None or said is None:
        return

    standing = person.question
    if standing is None:
        return

    with suppress(ValidationError):
        answer = Answer.model_validate(said)
        person.answer(answer.number, _read_as(standing.asked_for, answer.answered))


def _read_as(asked_for: AskedFor, answered: dict[str, Any]) -> Reflection:
    """The answer, read as the shape the question asked for."""
    if asked_for is AskedFor.TURN:
        return Turn.model_validate(answered)
    return Reflection.model_validate(answered)
