"""Scripted agents.

They exist so the whole game is playable, and testable, without a single model
call (GL-2). Their only hard obligation: never produce an intent the engine
would refuse.
"""

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, RandomAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.intents import IntentKind, TakeTurn, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, TableOptions
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import project

SIX_SEATS = GameRules(table=TableOptions(player_count=6))


def every_phase_of_a_game() -> list[GameState]:
    """A game state in each phase where agents are asked to act."""
    night_zero = create_game(SIX_SEATS, rng=create_rng(3))
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
async def test_agents_only_ever_produce_legal_intents(agent: Agent) -> None:
    for state in every_phase_of_a_game():
        for player in state.living:
            intent = (await agent.decide(project(state, player.id))).intent

            validate_intent(state, player.id, intent)


@pytest.mark.parametrize("agent", agents(), ids=lambda agent: type(agent).__name__)
async def test_agents_stay_silent_once_they_have_voted(agent: Agent) -> None:
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    voter = state.living[0].id
    state = state.with_ballot_from(voter, state.living[1].id)

    assert (await agent.decide(project(state, voter))).intent == Wait()


async def test_the_silent_agent_never_speaks_nor_names_anyone() -> None:
    agent = SilentAgent()

    for state in every_phase_of_a_game():
        for player in state.living:
            intent = (await agent.decide(project(state, player.id))).intent

            assert intent.kind in {IntentKind.WAIT, IntentKind.TAKE_TURN}
            if isinstance(intent, TakeTurn):
                assert intent.speech is None, "it never speaks"
                assert intent.vote is not None, "a turn it takes is always a vote"
                assert intent.vote.is_blank, "and never names anyone"


async def test_the_accusing_agent_names_someone_as_soon_as_it_may() -> None:
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    accuser = state.living[0].id

    intent = (await AlwaysAccuseAgent().decide(project(state, accuser))).intent

    assert isinstance(intent, TakeTurn)
    assert intent.vote is not None
    assert intent.vote.target is not None
    assert intent.vote.target != accuser


async def test_the_accusing_agent_falls_back_to_a_blank_vote_on_the_first_day() -> None:
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=1)
    accuser = state.living[0].id

    intent = (await AlwaysAccuseAgent().decide(project(state, accuser))).intent

    assert isinstance(intent, TakeTurn)
    assert intent.vote is not None
    assert intent.vote.is_blank


async def lines_of(state: GameState, speaker: PlayerId, seeds: range = range(30)) -> list[str]:
    """Every line one seat produces over a run of seeds.

    Swept rather than pinned to one seed: what a turn does is now drawn in
    several steps (D-028), so a single draw says nothing about the agent and
    would break on any change to the order of its choices.
    """
    turns = [
        (await RandomAgent(rng=create_rng(seed)).decide(project(state, speaker))).intent
        for seed in seeds
    ]
    return [turn.speech for turn in turns if isinstance(turn, TakeTurn) and turn.speech is not None]


async def test_the_random_agent_speaks_even_with_nobody_left_to_suspect() -> None:
    """Degenerate but reachable: speech must never depend on someone else existing."""
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    lonely = state.living[0].id
    state = state.with_players_killed(player.id for player in state.living[1:])

    lines = await lines_of(state, lonely)

    assert lines, "it still finds something to say"
    for line in lines:
        assert not any(player.name in line for player in state.players), (
            "there is nobody left to name"
        )


async def test_the_random_agent_names_a_player_by_their_name_not_their_identifier() -> None:
    """A line joins the shared transcript: it is read on screen, and by the models (J7)."""
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    speaker = state.living[0]
    others = [other for other in state.players if other.id != speaker.id]

    lines = await lines_of(state, speaker.id)

    assert any(other.name in line for line in lines for other in others), "somebody gets named"
    for line in lines:
        assert not any(other.id in line for other in state.players), (
            "and never by an internal identifier"
        )


async def test_the_random_agent_is_reproducible_for_a_given_seed() -> None:
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    view = project(state, state.living[0].id)

    first = [(await RandomAgent(rng=create_rng(5)).decide(view)).intent for _ in range(10)]
    second = [(await RandomAgent(rng=create_rng(5)).decide(view)).intent for _ in range(10)]

    assert first == second


async def test_the_random_agent_does_not_always_answer_the_same_thing() -> None:
    state = create_game(SIX_SEATS, rng=create_rng(3)).entering(Phase.DAY, day=2)
    view = project(state, state.living[0].id)
    agent = RandomAgent(rng=create_rng(5))

    answers = {((await agent.decide(view)).intent).kind for _ in range(30)}

    assert len(answers) > 1
