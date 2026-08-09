"""Seating a table of models from the configuration (D-058, D-064, D-077)."""

from lupus_ex_machina.configuration.agents import AgentOptions, Personality, SeatProfile
from lupus_ex_machina.configuration.system import SystemOptions
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


def test_a_seat_is_held_to_the_window_declared_for_the_model_it_generates_with() -> None:
    """The budget of D-063 reaches the seats, or the mechanism is never used.

    Read off the *generation* model: the auction runs on the other one, and it
    is the turn that carries a game's history (D-077).
    """
    state = create_game(GameRules(), rng=create_rng(4))
    declared = SystemOptions(
        context_windows={SeatProfile().generation_model: 100_000}, context_margin=0.5
    )

    agents = seat_agents(
        state, AgentOptions(), completions=FakeCompletions(), seed=1, system=declared
    )

    assert agents[state.players[0].id].budget.tokens == 50_000


def test_a_table_whose_models_declare_no_window_is_never_pruned() -> None:
    """The default of V1: nothing is declared, so nothing is ever cut."""
    state = create_game(GameRules(), rng=create_rng(4))

    agents = seat_agents(state, AgentOptions(), completions=FakeCompletions(), seed=1)

    assert all(agent.budget.tokens is None for agent in agents.values())


def test_the_same_seed_deals_the_same_temperaments() -> None:
    """Everything a game does comes from one seed, temperaments included."""
    state = create_game(GameRules(), rng=create_rng(4))

    def dealt(seed: int) -> list[Personality]:
        agents = seat_agents(state, AgentOptions(), completions=FakeCompletions(), seed=seed)
        return [agents[player.id].personality.code for player in state.players]

    assert dealt(7) == dealt(7)
    assert dealt(7) != dealt(8)
