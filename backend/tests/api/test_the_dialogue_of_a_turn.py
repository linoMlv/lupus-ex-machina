"""The one thing that travels upward: a question, and its answer (J8.5.6, D-109).

The stream is one-way in spirit. What comes back is how far a client has shown,
and what its player answers — nothing else, because nothing else belongs to a
connection: the buttons and the moderator's hand outlive one, and one of them
works in a mode where nobody is ever asked anything.
"""

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.hosting.protocol import ANSWER, SHOWN, AskedFor, QuestionState
from support.clients import game_of, logged_in

#: Messages to read before giving up. Wide enough to reach the end of a round,
#: which is where the second kind of question is put.
LONG_ENOUGH = 400


def a_question_on(
    stream: WebSocketTestSession,
    *,
    hand: RandomAgent | None = None,
    wanted: AskedFor | None = None,
) -> dict[str, Any]:
    """Read the stream until the game asks the kind of thing that was wanted.

    Answers whatever is asked along the way when given a hand. That is what it
    takes to reach a stock-taking at all: it comes once a round has closed, and
    a round does not close while the table is waiting on somebody.
    """
    for _ in range(LONG_ENOUGH):
        said: dict[str, Any] = stream.receive_json()
        if said["events"]:
            stream.send_json({SHOWN: said["events"][-1]["sequence"]})

        question: dict[str, Any] | None = said.get("question")
        if question is None or question["state"] != QuestionState.PUT:
            continue
        if wanted is None or question["asked_for"] == wanted:
            return question
        if hand is not None:
            stream.send_json({ANSWER: answered_by(question, hand)})
    raise AssertionError("the stream never said the game was waiting on anybody")


def answered_by(question: dict[str, Any], hand: RandomAgent) -> dict[str, Any]:
    """A legal answer to that question, drawn from the view it carries."""
    view = PlayerView.model_validate(question["view"])
    asked_for = AskedFor(question["asked_for"])
    answer = asyncio.run(
        hand.decide(view, ()) if asked_for is AskedFor.TURN else hand.reflect(view, ())
    )
    return {"number": question["number"], "answered": answer.model_dump(mode="json")}


def playing(client: TestClient) -> None:
    client.post("/api/game/start")


def test_the_stream_says_what_the_game_is_waiting_on_its_player_for() -> None:
    with logged_in(playing=True) as client:
        playing(client)

        with client.websocket_connect("/api/game/stream") as stream:
            question = a_question_on(stream)

    assert question["asked_for"] == AskedFor.TURN
    assert question["view"]["self_id"] == "player-0", "their own view, and the seat they took"


def test_an_answer_sent_up_the_stream_is_the_move_the_engine_plays() -> None:
    """The whole path, end to end: asked over the wire, answered over the wire."""
    with logged_in(playing=True) as client:
        playing(client)

        with client.websocket_connect("/api/game/stream") as stream:
            question = a_question_on(stream)
            stream.send_json({ANSWER: answered_by(question, RandomAgent(rng=create_rng(4)))})

            went_on = a_question_on(stream)

    assert went_on["number"] > question["number"], "the game moved on to asking something else"


def test_a_stock_taking_is_answered_over_the_wire_just_as_a_turn_is() -> None:
    """The other of the two questions (D-086, D-108) — the notebook moment.

    Read as a stock-taking because the **question** said so, never because of
    what arrived: a turn offered here is refused rather than taken with its move
    quietly dropped, a turn being a stock-taking with a move on it.
    """
    hand = RandomAgent(rng=create_rng(4))
    with logged_in(playing=True) as client:
        playing(client)

        with client.websocket_connect("/api/game/stream") as stream:
            question = a_question_on(stream, hand=hand, wanted=AskedFor.REFLECTION)
            stream.send_json({ANSWER: answered_by(question, hand)})

            went_on = a_question_on(stream, hand=hand)

    assert went_on["number"] > question["number"], "the game took the answer and moved on"


def test_a_client_arriving_while_a_question_stands_is_told_about_it() -> None:
    """A question put before this client existed was announced to nobody.

    Without this, refreshing a browser at the wrong moment leaves a person in
    front of a game that is waiting on them and says nothing — the gap between a
    history and a subscription that D-102 closes for the facts.
    """
    with logged_in(playing=True) as client:
        playing(client)
        with client.websocket_connect("/api/game/stream") as first:
            standing = a_question_on(first)

        with client.websocket_connect("/api/game/stream") as second:
            told = a_question_on(second)

    assert told["number"] == standing["number"], "the same question, said again to whoever asks"


def test_a_malformed_answer_is_ignored_and_leaves_the_question_standing() -> None:
    """So the client has only to send again, which is what makes ignoring it safe."""
    with logged_in(playing=True) as client:
        playing(client)

        with client.websocket_connect("/api/game/stream") as stream:
            question = a_question_on(stream)
            stream.send_json({ANSWER: {"number": question["number"], "answered": {"quoi": 1}}})
            stream.send_json({SHOWN: 0})

            person = game_of(client).person
            assert person is not None
            standing = person.question

    assert standing is not None, "the game is still waiting"
    assert standing.number == question["number"], "on the very same question"


def test_an_answer_arriving_when_nothing_is_asked_is_ignored() -> None:
    """A tab that was slow answers a moment the game has left, or not yet reached.

    There is nothing for it to be an answer to, so it moves nothing along. Sent
    here before the game was even started, which is the one moment the race is
    not a race.
    """
    with (
        logged_in(playing=True) as client,
        client.websocket_connect("/api/game/stream") as stream,
    ):
        stream.send_json({ANSWER: {"number": 1, "answered": {"intent": {"kind": "wait"}}}})
        playing(client)

        question = a_question_on(stream)

    assert question["number"] == 1, "the first question is put, and still waits on a real answer"


def test_a_stray_message_neither_answers_nor_ends_anything() -> None:
    """The stream is one-way in spirit: nothing a client says may end a game."""
    with logged_in(playing=True) as client:
        playing(client)

        with client.websocket_connect("/api/game/stream") as stream:
            question = a_question_on(stream)
            stream.send_json(["ni un fait, ni une réponse"])
            stream.send_json({"inconnu": True})
            stream.send_json({ANSWER: answered_by(question, RandomAgent(rng=create_rng(4)))})

            went_on = a_question_on(stream)

    assert went_on["number"] > question["number"]
