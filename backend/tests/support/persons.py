"""Games dealt with somebody at the table (J8.5)."""

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameMode, GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.views import PlayerView, project

#: The short game of the other hosting tests, dealt from a seat instead of
#: watched. Seat zero is the first the opening night wakes, so a game of this
#: shape meets its person at the very first thing it asks anybody.
PLAYED_FROM_SEAT_ZERO = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4, mode=GameMode.PLAYER, human_seat=0),
        night=NightOptions(require_werewolf_target=True),
    )
)


def a_view_at_the_floor() -> PlayerView:
    """A seat's view of a day it may speak in, which is where a request is spent."""
    state = create_game(rng=create_rng(4)).entering(Phase.DAY, day=1)
    return project(state, state.players[0].id)


def a_view_of_the_opening_night() -> PlayerView:
    """A seat's view of a night nobody speaks in (D-083)."""
    state = create_game(rng=create_rng(4))
    return project(state, state.players[0].id)
