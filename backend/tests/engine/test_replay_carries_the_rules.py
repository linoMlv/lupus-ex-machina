"""A journal is replayed under the rules its game was played by (found in J8.3).

Rules are not facts, so they are not in the journal (D-040) — a replay has to be
told them. Until it was, a replayed state came back under **default** rules, and
every question asked of it was answered by a game nobody played.

It went unnoticed because the games that were replayed were dealt with the
defaults, so the wrong answer and the right one agreed. J8 asked the first
question where they differ: who a game is projected for is read off its mode
(D-100), and a replayed state said "spectator" about a game somebody was
playing — the whole journal to a player who may see a fraction of it.
"""

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameMode, GameRules, InformationOptions, TableOptions
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game

PLAYED_BY_A_HUMAN = GameRules(
    table=TableOptions(player_count=6, seed=4, mode=GameMode.PLAYER, human_seat=0),
    information=InformationOptions(reveal_everything_to_the_dead=False),
)


async def a_played_journal(rules: GameRules) -> Journal:
    """A whole game, played under those rules, with its journal kept."""
    rng = create_rng(rules.table.seed)
    state = create_game(rules, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    journal = Journal()
    await play_game(state, agents, journal=journal, rng=rng)
    return journal


async def test_a_replayed_game_is_played_under_the_rules_it_is_given() -> None:
    journal = await a_played_journal(PLAYED_BY_A_HUMAN)

    rebuilt = replay(journal.events, rules=PLAYED_BY_A_HUMAN)

    assert rebuilt.rules == PLAYED_BY_A_HUMAN


async def test_a_replay_told_nothing_falls_back_on_the_defaults() -> None:
    """Which is right for a caller who has no rules to give, and only then."""
    journal = await a_played_journal(GameRules(table=TableOptions(player_count=6, seed=4)))

    assert replay(journal.events).rules == GameRules()


async def test_the_state_of_a_replay_is_the_state_the_game_reached() -> None:
    """The property J3 rests on, unchanged: rules are added, nothing else moves."""
    rules = PLAYED_BY_A_HUMAN
    rng = create_rng(rules.table.seed)
    state = create_game(rules, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    journal = Journal()
    result = await play_game(state, agents, journal=journal, rng=rng)

    assert replay(journal.events, rules=rules) == result.state
