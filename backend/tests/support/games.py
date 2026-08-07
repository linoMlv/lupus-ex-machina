"""Dealing a game, playing one, and reading what came out of it.

Shared by the modules that exercise the runner. Each of them keeps the agents
and the extractors that only it uses; what is here is what several of them ask
for.
"""

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.composition import MAXIMUM_PLAYERS, MINIMUM_PLAYERS
from lupus_ex_machina.engine.events import Event, SpeechDelivered
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.victory import evaluate_victory

PLAYER_COUNTS = range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1)

#: A pack made to leave the night with a victim (D-078), which is what sends it
#: to the lot when it cannot agree (D-081).
FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


def seats(count: int, rules: GameRules | None = None) -> GameRules:
    """The same rules, dealt to a table of that size."""
    settled = rules if rules is not None else GameRules()
    return settled.model_copy(
        update={"table": settled.table.model_copy(update={"player_count": count})}
    )


def six_seats(rules: GameRules | None = None) -> GameRules:
    """The smallest table V1 deals (D-056)."""
    return seats(6, rules)


async def play(seed: int, *, player_count: int = 8) -> GameResult:
    """Play one full game of random agents, everything derived from one seed."""
    rng = create_rng(seed)
    state = create_game(seats(player_count), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return await play_game(state, agents)


def assert_properly_finished(result: GameResult) -> None:
    """Check a game really ended, rather than merely returning.

    ``result.outcome`` is typed as :class:`Outcome` and validated on
    construction, so asserting it *is* one proves nothing. What is worth
    checking is that the reported winner is the one the final state gives, and
    that the game was closed rather than abandoned mid-round.
    """
    assert result.state.phase is Phase.ENDED
    assert result.rounds >= 1
    assert evaluate_victory(result.state) is result.outcome


def speakers_of(events: tuple[Event, ...]) -> list[PlayerId]:
    """Who took the floor, in the order they took it."""
    return [event.payload.speaker for event in events if isinstance(event.payload, SpeechDelivered)]
