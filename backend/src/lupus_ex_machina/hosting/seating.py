"""Who plays which seat, once a game has been dealt (J8.5, D-096).

Apart from what a person's seat *is*: this answers whether a game has one at
all, and hands the table back with them in it. The mode is fixed at creation
(D-100), so both answers are settled once, when the game is dealt, rather than
asked again at every turn.
"""

from collections.abc import Mapping

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rules import GameMode
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.hosting.human import Announce, HumanAgent


def the_person_at(
    configuration: GameConfiguration, state: GameState, *, announce: Announce
) -> HumanAgent | None:
    """The agent playing the seat a person occupies, when a game has one.

    Nothing at all in spectator mode: there is no seat to play, and there never
    will be one — which is what makes "is there somebody to ask" a property of
    the game rather than a question put again at every turn.
    """
    table = configuration.rules.table
    if table.mode is not GameMode.PLAYER or table.human_seat is None:
        return None

    seated = next(player for player in state.players if player.seat == table.human_seat)
    return HumanAgent(seated.id, announce=announce, timeout=table.human_answer_timeout_seconds)


def seated_with(
    agents: Mapping[PlayerId, Agent], person: HumanAgent | None
) -> Mapping[PlayerId, Agent]:
    """The table of agents, with the person in the seat that is theirs.

    Laid over a whole table rather than carved out of the seating itself: the
    seating of J7 reads what each seat was configured with, and a seat left out
    of it would be a hole in the one place that knows how a table is made up.
    """
    return agents if person is None else {**agents, person.player: person}
