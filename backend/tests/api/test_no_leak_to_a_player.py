"""J8.3.3 — the critical test: everything a player is sent, and nothing else.

The whole traffic of a whole game, captured and compared against the projection
of that game's journal. Stated that way it cannot be fooled by a name: a leak
under any field, in any fact, makes the two differ.

**Played with the dead kept in the dark** (D-105 off). Left on, the human becomes
the spectator the moment their character dies, and the assertion would be vacuous
from the first death onwards — the shape of hollow test this project has met
four times.

Three things are asserted before the comparison, for the same reason. That the
game ran to its end, so the capture is of a whole game rather than a corner of
one. That it produced facts a player must not see. And that it produced some
they must. A property over an empty set is true and worth nothing.
"""

from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.hosting.audience import recipient_for
from lupus_ex_machina.hosting.stage import Stage
from support.clients import followed_to_the_end, game_of, logged_in


def test_a_player_is_sent_their_projection_and_not_one_fact_more() -> None:
    with logged_in(playing=True) as client:
        client.post("/api/game/start")

        sent = followed_to_the_end(client)

        game = game_of(client)
        recorded = tuple(game.events)
        theirs = project_journal(recorded, recipient_for(game.state))

    assert game.stage is Stage.OVER, "a whole game, not a corner of one"
    assert len(recorded) > len(theirs), "the game produced facts this player may not see"
    assert theirs, "and some they may — comparing two empty lists proves nothing"
    assert [event["sequence"] for event in sent] == [event.sequence for event in theirs]
