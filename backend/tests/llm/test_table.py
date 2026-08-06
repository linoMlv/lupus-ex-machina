"""Seating a table of models from the configuration (D-058, D-064, D-077)."""

from lupus_ex_machina.configuration.agents import AgentOptions, Personality, SeatProfile
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.table import seat_agents


def a_table() -> tuple[GameRules, list[str]]:
    rules = GameRules()
    state = create_game(rules, rng=create_rng(4))
    return rules, [player.id for player in state.players]


def test_every_seat_of_the_table_is_given_an_agent() -> None:
    rules, seated = a_table()
    state = create_game(rules, rng=create_rng(4))

    agents = seat_agents(state, AgentOptions(), completions=FakeCompletions(), seed=1)

    assert set(agents) == set(seated)


def test_a_seat_configured_apart_is_played_the_way_it_was_configured() -> None:
    """The asymmetries D-058 exists for: two models at one table, deliberately."""
    state = create_game(GameRules(), rng=create_rng(4))
    options = AgentOptions(
        seats={
            1: SeatProfile(
                bidding_model="ministral-8b-latest",
                generation_model="mistral-large-latest",
                personality=Personality.ESTP,
            )
        }
    )

    agents = seat_agents(state, options, completions=FakeCompletions(), seed=1)

    apart = agents[state.players[1].id]
    default = agents[state.players[0].id]
    assert apart.generation_model == "mistral-large-latest"
    assert apart.personality.code is Personality.ESTP
    assert default.generation_model == SeatProfile().generation_model


def test_a_seat_nobody_configured_is_dealt_a_temperament_rather_than_left_without() -> None:
    """D-064: random by default, so a table is never sixteen copies of one voice."""
    state = create_game(GameRules(), rng=create_rng(4))

    agents = seat_agents(state, AgentOptions(), completions=FakeCompletions(), seed=1)

    assert len({agent.personality.code for agent in agents.values()}) > 1


def test_the_same_seed_deals_the_same_temperaments() -> None:
    """Everything a game does comes from one seed, temperaments included."""
    state = create_game(GameRules(), rng=create_rng(4))

    def dealt(seed: int) -> list[Personality]:
        agents = seat_agents(state, AgentOptions(), completions=FakeCompletions(), seed=seed)
        return [agents[player.id].personality.code for player in state.players]

    assert dealt(7) == dealt(7)
    assert dealt(7) != dealt(8)
