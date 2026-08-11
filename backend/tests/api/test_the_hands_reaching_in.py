"""The buttons and the moderator's hand, as routes (J8.5.1, J8.5.4, D-109).

Routes rather than websocket messages, and the reason is in what they are. They
outlive a connection, and the moderator's works **in both modes** (D-048) — so
in one where nothing is ever sent upward at all. The websocket carries the
dialogue of a turn: the question, and the answer to it. Nothing else.
"""

import asyncio

from fastapi import status
from fastapi.testclient import TestClient

from lupus_ex_machina.hosting.human import WANTS_NOTHING, WANTS_THE_FLOOR
from support.clients import PLAYED, WATCHED, game_of, logged_in
from support.persons import a_view_at_the_floor


def a_watched_game(client: TestClient) -> None:
    """Deal a game nobody sits at, which is where the moderator's hand still works."""
    client.post("/api/game", json=WATCHED)


def test_the_person_may_ask_for_the_floor() -> None:
    with logged_in(playing=True) as client:
        answered = client.post("/api/game/floor/request")

        assert answered.status_code == status.HTTP_204_NO_CONTENT


def test_the_person_may_take_the_floor_outright() -> None:
    with logged_in(playing=True) as client:
        answered = client.post("/api/game/floor/claim")

        assert answered.status_code == status.HTTP_204_NO_CONTENT


def test_neither_button_answers_for_a_game_nobody_sits_at() -> None:
    """Refused out loud: a button that answers and does nothing looks like a bug."""
    with logged_in() as client:
        a_watched_game(client)

        for button in ("/api/game/floor/request", "/api/game/floor/claim"):
            answered = client.post(button)

            assert answered.status_code == status.HTTP_409_CONFLICT, button
            assert answered.json()["detail"], "and it says why"


def test_the_moderator_may_call_time_on_a_debate_of_a_watched_game() -> None:
    """The hand D-048 was written for, in the mode that has nobody to ask."""
    with logged_in() as client:
        a_watched_game(client)

        answered = client.post("/api/game/debate", json={"turns": 0})

        assert answered.status_code == status.HTTP_202_ACCEPTED
        assert answered.json() == {"turns_left": 0}
        assert game_of(client).hands.debate_turns_left == 0


def test_the_moderator_may_lengthen_a_debate_as_well_as_shorten_one() -> None:
    with logged_in() as client:
        a_watched_game(client)

        assert client.post("/api/game/debate", json={"turns": 12}).json() == {"turns_left": 12}


def test_a_negative_allowance_is_refused_rather_than_read_as_nought() -> None:
    """Zero already means "vote now"; below it means nothing anyone could want."""
    with logged_in() as client:
        a_watched_game(client)

        answered = client.post("/api/game/debate", json={"turns": -1})

        assert answered.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_the_hands_reach_for_a_game_that_is_there() -> None:
    """No game is a plain refusal, like everywhere else on this API."""
    with logged_in() as client:
        assert client.post("/api/game/floor/claim").status_code == status.HTTP_404_NOT_FOUND
        assert (
            client.post("/api/game/debate", json={"turns": 0}).status_code
            == status.HTTP_404_NOT_FOUND
        )


def test_asking_for_the_floor_is_what_bids_for_it() -> None:
    """The route works the very button the auction reads (D-107).

    Asserted on the bid rather than on the status: a route that answered 204 and
    reached the wrong hand would look exactly the same from outside.
    """
    with logged_in() as client:
        client.post("/api/game", json=PLAYED)
        person = game_of(client).person
        assert person is not None
        assert asyncio.run(person.bid(a_view_at_the_floor(), ())).urgency == WANTS_NOTHING

        client.post("/api/game/floor/request")

        assert asyncio.run(person.bid(a_view_at_the_floor(), ())).urgency == WANTS_THE_FLOOR
