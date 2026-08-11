"""A client of a running application, already through the door (J8).

**Used as a context manager, always.** A `TestClient` built without one starts
and stops a portal for every single request, which cancels the task a game is
playing in: the game freezes wherever it was, and a test reading the traffic
gets a fraction of a game while believing it read all of one. Inside a block,
the loop lives for as long as the block does — which is what a real server does
for as long as it runs.
"""

import asyncio
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any, NamedTuple

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.hosting import GameHost, HostedGame
from lupus_ex_machina.hosting.host import Provider
from lupus_ex_machina.hosting.protocol import ANSWER, SHOWN, AskedFor, QuestionState
from lupus_ex_machina.llm.completions import Answer, Asked, Completions
from lupus_ex_machina.llm.messages import Message
from lupus_ex_machina.llm.throttling import Waiting
from support.hosted import a_completions

PASSWORD = "ouvre-toi"

#: Six players, a pack made to leave with a victim, and a game watched from
#: outside. Short enough to play in a test, long enough to be a real game.
WATCHED: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4},
        "night": {"require_werewolf_target": True},
    }
}

#: The same game, played from seat zero, with the dead learning nothing more —
#: which is what keeps a leak test meaningful past the first death (D-105).
PLAYED: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4, "mode": "player", "human_seat": 0},
        "information": {"reveal_everything_to_the_dead": False},
        "night": {"require_werewolf_target": True},
    }
}


@contextmanager
def logged_in(*, playing: bool = False, waiting_for: float | None = None) -> Iterator[TestClient]:
    """A client through the door, of an application whose models reach nobody.

    A provider may be made to announce a wait as a rate limited one does, which
    is how the whole chain of D-066 is exercised from its source.
    """
    app = create_app(Settings(password=PASSWORD, secret_key="clef"), provider=_waits(waiting_for))
    with TestClient(app) as client:
        client.post("/api/session", json={"password": PASSWORD})
        if playing:
            client.post("/api/game", json=PLAYED)
        yield client


def game_of(client: TestClient) -> HostedGame:
    """The game the application behind that client is hosting.

    Asserted rather than returned as an optional: a test that reached for a game
    that is not there wants to say so loudly, not to check for None.
    """
    host: GameHost = client.app.state.host  # type: ignore[attr-defined]
    hosted = host.current
    assert hosted is not None, "the application is hosting no game"
    return hosted


class Followed(NamedTuple):
    """Everything that travelled to one client over a whole game.

    The questions are kept apart from the facts because they are not facts: a
    question says what the game is waiting on its player for, and carries their
    view rather than a sequence (D-096). Kept all the same — a capture that
    dropped them would no longer be a capture of the whole traffic, which is
    what the critical test of J8.3.3 rests on being.
    """

    events: list[dict[str, Any]]
    questions: list[dict[str, Any]]


def followed_to_the_end(client: TestClient, hand: Agent | None = None) -> Followed:
    """Everything that travelled to that client, over a whole game.

    Confirms what it has shown as it goes, which is what a front end does and
    what lets the game go on: a hosted game runs a few turns ahead of its
    audience and waits once too many are in flight (J8.4). A reader that never
    confirmed would watch the game stop, which is the feature rather than a hang.

    Answers what it is asked, when given a hand to answer with. A played game
    waits on its person for as long as it takes (D-097), so a reader that never
    answered would watch it stop at its opening night — which is the feature
    too, and would leave a whole-game assertion with a corner of one to check.

    Reads until the server hangs up, which it does once the game has nothing
    more to say. Catching anything wider would let a broken socket read as a
    finished game, and the capture would fall short of what it is checking.
    """
    followed = Followed(events=[], questions=[])
    with client.websocket_connect("/api/game/stream") as stream, suppress(WebSocketDisconnect):
        while True:
            said = stream.receive_json()
            followed.events.extend(said["events"])
            if said["events"]:
                stream.send_json({SHOWN: said["events"][-1]["sequence"]})
            if (question := said.get("question")) is not None:
                followed.questions.append(question)
                _answer(stream, question, hand)
    return followed


def _answer(stream: WebSocketTestSession, question: dict[str, Any], hand: Agent | None) -> None:
    """Answer a question with that hand, as a front end would on somebody's behalf.

    A scripted agent rather than a policy written here: what a person answers
    has to be a legal move like any other, and the agents of J2 already know how
    to draw one from a view. A question being closed is not asked, so nothing is
    answered to it.
    """
    if hand is None or question["state"] != QuestionState.PUT:
        return

    view = PlayerView.model_validate(question["view"])
    asked_for = AskedFor(question["asked_for"])
    answered = asyncio.run(
        hand.decide(view, ()) if asked_for is AskedFor.TURN else hand.reflect(view, ())
    )
    stream.send_json(
        {ANSWER: {"number": question["number"], "answered": answered.model_dump(mode="json")}}
    )


def _waits(seconds: float | None) -> Provider:
    """A way of building a provider that announces a wait, as a throttled one does.

    Announced on the first question rather than on construction: a client is
    built long before a game asks it anything, and a wait announced to an empty
    room is a wait nobody could have been shown.
    """

    def built(system: SystemOptions, waiting: Waiting) -> Completions:
        inner = a_completions()
        return inner if seconds is None else _Announcing(inner, waiting, seconds)

    return built


class _Announcing:
    """A provider that says it is waiting, once, before answering anything."""

    def __init__(self, inner: Completions, waiting: Waiting, seconds: float) -> None:
        """Take who really answers, who to tell, and how long to claim."""
        self._inner = inner
        self._waiting = waiting
        self._seconds = seconds
        self._said = False

    @property
    def asked(self) -> Sequence[Asked]:
        """What was asked, straight from whoever really answers."""
        return self._inner.asked

    @property
    def seconds_spent(self) -> float:
        """How long that took, straight from whoever really answers."""
        return self._inner.seconds_spent

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> Answer:
        """Announce the wait once, then answer as the inner provider would."""
        if not self._said:
            self._said = True
            self._waiting(self._seconds)
        return await self._inner.complete(
            model=model, messages=messages, schema=schema, temperature=temperature, top_p=top_p
        )
