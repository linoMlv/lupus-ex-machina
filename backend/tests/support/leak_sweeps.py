"""Playing whole games and sweeping everything they recorded, for leaks (J3.2)."""

from collections.abc import Iterable, Iterator

from lupus_ex_machina.agents.scripted import RandomAgent, RogueAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    Event,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient

#: Wide enough that every rule of the game gets exercised, small enough to stay
#: a second of test time.
CORPUS = range(100)

#: A handful of games for the properties that inspect every value of every
#: projection, which costs more than counting events.
SAMPLE = range(12)


async def played(seed: int, *, rules: GameRules | None = None) -> GameResult:
    """Play one full game of random agents, journalling everything."""
    rng = create_rng(seed)
    state = create_game(rules, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return await play_game(state, agents, journal=Journal())


async def played_with_a_rogue(seed: int) -> GameResult:
    """A game where one seat keeps playing intents the rules refuse.

    The well-behaved agents never produce one, so without this the property
    below would hold over an empty set and prove nothing.
    """
    rng = create_rng(seed)
    state = create_game(rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }
    return await play_game(state, agents, journal=Journal())


def everyone_at(state: GameState) -> list[Recipient]:
    """Every recipient a projection can be built for, the spectator included."""
    return [Recipient.of(player) for player in state.players] + [SPECTATOR]


def scalars_in(value: object) -> Iterator[object]:
    """Every leaf of a serialised structure, however deeply it is nested.

    This is what makes "in no form at all" testable: a secret that surfaced as a
    count, a list length or a stray field is a leaf like any other.
    """
    match value:
        case dict():
            for nested in value.values():
                yield from scalars_in(nested)
        case list() | tuple():
            for nested in value:
                yield from scalars_in(nested)
        case _:
            yield value


def leaves_of(events: Iterable[Event]) -> set[object]:
    """Every value a recipient could read off their projection."""
    return {leaf for event in events for leaf in scalars_in(event.model_dump(mode="json"))}


def payloads_of(events: Iterable[Event], kind: type) -> list[Event]:
    return [event for event in events if isinstance(event.payload, kind)]
