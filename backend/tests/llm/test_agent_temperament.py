"""What a seat is configured with, and what it changes (J7.6, D-058, D-064)."""

import json

from lupus_ex_machina.configuration.agents import Personality
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import DropNote
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.llm.answers import (
    TurnAnswer,
)
from lupus_ex_machina.llm.fake import FakeCompletions
from support.seats import FORCED, seated

# --- What a seat is configured with, and what it changes (J7.6, D-058, D-064) -


async def test_an_extravert_bids_higher_than_an_introvert_on_the_same_answer() -> None:
    """D-064: a temperament shifts the auction, it does not merely colour the prose."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    view = project(state, state.players[0].id)
    answered = json.dumps({"urgency": 50, "intention": "Parler."})

    outspoken = await seated(FakeCompletions(script=[answered]), Personality.ENFP).bid(view, ())
    reserved = await seated(FakeCompletions(script=[answered]), Personality.INTJ).bid(view, ())

    assert outspoken.urgency > reserved.urgency


async def test_an_urgency_never_leaves_its_scale_whatever_the_temperament() -> None:
    """The bias is applied to a number the auction reads, so it stays a number it can read."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    view = project(state, state.players[0].id)

    highest = await seated(
        FakeCompletions(script=[json.dumps({"urgency": 100, "intention": "Tout."})]),
        Personality.ENFP,
    ).bid(view, ())
    lowest = await seated(
        FakeCompletions(script=[json.dumps({"urgency": 0, "intention": "Rien."})]),
        Personality.INTJ,
    ).bid(view, ())

    assert (highest.urgency, lowest.urgency) == (100, 0)


async def test_a_note_a_model_strikes_out_survives_the_trimming_untouched() -> None:
    """A deletion carries no text, which is why it is its own type (D-005)."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Cette note ne vaut plus rien.",
                notebook=(DropNote(entry=2),),
                votes_blank=True,
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(state, state.players[0].id), ())

    assert turn.notebook == (DropNote(entry=2),)


def test_a_seat_says_which_model_it_bids_with() -> None:
    """Read by the console command, and by the spectator later (D-077)."""
    agent = seated(FakeCompletions())

    assert agent.bidding_model == "ministral-3b-latest"
