"""J8.3.3 — the critical test: everything a player is sent, and nothing else.

The whole traffic of a whole game, captured and compared against the projection
of that game's journal. Stated that way it cannot be fooled by a name: a leak
under any field, in any fact, makes the two differ.

**Played with the dead kept in the dark** (D-105 off). Left on, the human becomes
the spectator the moment their character dies, and the assertion would be vacuous
from the first death onwards — the shape of hollow test this project has met
four times.

**Played by somebody who answers** (J8.5). A game dealt from a seat waits on its
person for as long as it takes (D-097), so a reader that only watched would
capture the opening night and call it a game.

The traffic is now two things, and both are checked. The **facts**, against the
projection of the journal. And the **questions**, which carry a view rather than
a sequence: a channel left out of the capture would narrow this test without
anybody noticing.

Three things are asserted before the comparison, for the same reason. That the
game ran to its end, so the capture is of a whole game rather than a corner of
one. That it produced facts a player must not see. And that it produced some
they must. A property over an empty set is true and worth nothing.
"""

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.hosting.audience import recipient_for
from lupus_ex_machina.hosting.protocol import QuestionState
from lupus_ex_machina.hosting.stage import Stage
from support.clients import followed_to_the_end, game_of, logged_in
from support.leak_sweeps import scalars_in


def test_a_player_is_sent_their_projection_and_not_one_fact_more() -> None:
    with logged_in(playing=True) as client:
        client.post("/api/game/start")

        sent = followed_to_the_end(client, RandomAgent(rng=create_rng(4)))

        game = game_of(client)
        recorded = tuple(game.events)
        theirs = project_journal(recorded, recipient_for(game.state))

    assert game.stage is Stage.OVER, "a whole game, not a corner of one"
    assert len(recorded) > len(theirs), "the game produced facts this player may not see"
    assert theirs, "and some they may — comparing two empty lists proves nothing"
    assert [event["sequence"] for event in sent.events] == [event.sequence for event in theirs]


def test_no_question_put_to_a_player_carries_a_role_other_than_their_own() -> None:
    """The other half of the traffic (J8.5.6).

    A question carries the **view**, which is what says what may be done right
    now — legality lives with the validator and nowhere else (D-001). That view
    is the one an agent is handed, and it obeys the same visibility model as the
    journal (D-009), swept over whole games by `test_leaks_in_the_view`. What
    this adds is that the *wire* carries that one and no other.
    """
    with logged_in(playing=True) as client:
        client.post("/api/game/start")

        sent = followed_to_the_end(client, RandomAgent(rng=create_rng(4)))

        game = game_of(client)
        person = game.person
        assert person is not None
        seated = next(one for one in game.players if one.id == person.player)

    put = [asked for asked in sent.questions if asked["state"] == QuestionState.PUT]
    assert put, "the game asked its person things, so there is something to check"

    foreign = {role.value for role in RoleName} - {seated.role.value}
    for asked in put:
        assert asked["view"]["self_id"] == person.player, "their own view, never anybody else's"
        readable = set(scalars_in(asked["view"])) & foreign
        assert not readable, f"a question let them read {readable}"
