"""Playing a single debate day, without the game around it.

The day alone rather than a whole game: what the auction does is the thing under
test, and a game would drown it in nights and resolutions.
"""

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import DebateControl, FloorClaim
from lupus_ex_machina.engine.runner.day import play_day
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from support.agents import Insistent


async def a_day_of(
    urgencies: dict[int, int], claim: FloorClaim | None = None
) -> tuple[GameState, tuple[Event, ...]]:
    """Play one debate day where each seat bids the urgency it was given."""
    state = create_game(rng=create_rng(12))
    agents: dict[PlayerId, Agent] = {
        player.id: Insistent(urgencies[player.seat]) for player in state.players
    }
    return state, await a_day_played_by(agents, claim=claim, state=state)


async def a_day_played_by(
    agents: dict[PlayerId, Agent],
    control: DebateControl | None = None,
    claim: FloorClaim | None = None,
    *,
    state: GameState | None = None,
    rules: GameRules | None = None,
) -> tuple[Event, ...]:
    """Play one debate day with the given agents, and hand back its journal."""
    played = state if state is not None else create_game(rules, rng=create_rng(12))
    journal = Journal()
    scribe = Scribe(agents, journal, create_rng(3))

    await play_day(
        scribe,
        scribe.enter(played, Phase.DAY, day=2),
        control=control if control is not None else DebateControl(),
        claim=claim if claim is not None else FloorClaim(),
    )
    return journal.events
