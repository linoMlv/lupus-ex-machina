"""Scripted agents.

They exist so the whole game is playable, and testable, without a single model
call (GL-2). Their only hard obligation: never produce an intent the engine
would refuse.
"""

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, RandomAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.intents import CastVote, IntentKind, Speak, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import project


def every_phase_of_a_game() -> list[GameState]:
    """A game state in each phase where agents are asked to act."""
    night_zero = create_game(6, rng=create_rng(3))
    first_day = night_zero.entering(Phase.DAY, day=1)
    debate_day = first_day.entering(Phase.RESOLUTION).entering(Phase.DAY, day=2)
    night = debate_day.entering(Phase.RESOLUTION).entering(Phase.NIGHT)
    return [night_zero, first_day, debate_day, night]


def agents() -> list[Agent]:
    return [
        RandomAgent(rng=create_rng(11)),
        AlwaysAccuseAgent(),
        SilentAgent(),
    ]


@pytest.mark.parametrize("agent", agents(), ids=lambda agent: type(agent).__name__)
def test_agents_only_ever_produce_legal_intents(agent: Agent) -> None:
    for state in every_phase_of_a_game():
        for player in state.living:
            intent = agent.decide(project(state, player.id))

            validate_intent(state, player.id, intent)


@pytest.mark.parametrize("agent", agents(), ids=lambda agent: type(agent).__name__)
def test_agents_stay_silent_once_they_have_voted(agent: Agent) -> None:
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=2)
    voter = state.living[0].id
    state = state.with_ballot_from(voter, state.living[1].id)

    assert agent.decide(project(state, voter)) == Wait()


def test_the_silent_agent_never_speaks_nor_names_anyone() -> None:
    agent = SilentAgent()

    for state in every_phase_of_a_game():
        for player in state.living:
            intent = agent.decide(project(state, player.id))

            assert intent.kind in {IntentKind.WAIT, IntentKind.VOTE}
            if isinstance(intent, CastVote):
                assert intent.is_blank


def test_the_accusing_agent_names_someone_as_soon_as_it_may() -> None:
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=2)
    accuser = state.living[0].id

    intent = AlwaysAccuseAgent().decide(project(state, accuser))

    assert isinstance(intent, CastVote)
    assert intent.target is not None
    assert intent.target != accuser


def test_the_accusing_agent_falls_back_to_a_blank_vote_on_the_first_day() -> None:
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=1)
    accuser = state.living[0].id

    intent = AlwaysAccuseAgent().decide(project(state, accuser))

    assert isinstance(intent, CastVote)
    assert intent.is_blank


def test_the_random_agent_speaks_even_with_nobody_left_to_suspect() -> None:
    """Degenerate but reachable: speech must never depend on someone else existing."""
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=2)
    lonely = state.living[0].id
    state = state.with_players_killed(player.id for player in state.living[1:])

    intent = RandomAgent(rng=create_rng(2)).decide(project(state, lonely))

    assert isinstance(intent, Speak | CastVote | Wait)


def test_the_random_agent_is_reproducible_for_a_given_seed() -> None:
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=2)
    view = project(state, state.living[0].id)

    first = [RandomAgent(rng=create_rng(5)).decide(view) for _ in range(10)]
    second = [RandomAgent(rng=create_rng(5)).decide(view) for _ in range(10)]

    assert first == second


def test_the_random_agent_does_not_always_answer_the_same_thing() -> None:
    state = create_game(6, rng=create_rng(3)).entering(Phase.DAY, day=2)
    view = project(state, state.living[0].id)
    agent = RandomAgent(rng=create_rng(5))

    answers = {agent.decide(view).kind for _ in range(30)}

    assert len(answers) > 1
