"""Victory conditions, as decided in D-059.

The rule deliberately departs from the classic `wolves >= villagers`: at parity
the game keeps going, unless only two players remain. The three reference
scenarios below were given by the project owner and are authoritative.
"""

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory


def state_of(*roles: tuple[RoleName, bool]) -> GameState:
    """Build a state from (role, alive) pairs, one per seat."""
    players = tuple(
        Player(id=PlayerId(f"p{seat}"), name=f"Joueur {seat}", seat=seat, role=role, alive=alive)
        for seat, (role, alive) in enumerate(roles)
    )
    return GameState.initial(players)


def test_village_wins_when_no_wolf_is_left() -> None:
    state = state_of(
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, True),
        (RoleName.WEREWOLF, False),
    )

    assert evaluate_victory(state) is Outcome.VILLAGE_WINS


def test_wolves_win_when_they_outnumber_the_villagers() -> None:
    state = state_of(
        (RoleName.WEREWOLF, True),
        (RoleName.WEREWOLF, True),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, False),
    )

    assert evaluate_victory(state) is Outcome.WEREWOLVES_WIN


def test_wolves_win_at_parity_when_only_two_players_are_left() -> None:
    """Third reference scenario of D-059: one wolf against one villager."""
    state = state_of(
        (RoleName.WEREWOLF, True),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, False),
    )

    assert evaluate_victory(state) is Outcome.WEREWOLVES_WIN


def test_game_continues_at_parity_when_four_players_are_left() -> None:
    """Two wolves against two villagers keeps playing — this is the D-059 departure."""
    state = state_of(
        (RoleName.WEREWOLF, True),
        (RoleName.WEREWOLF, True),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, True),
    )

    assert evaluate_victory(state) is None


def test_game_continues_while_wolves_are_outnumbered() -> None:
    """Second reference scenario of D-059, once the hunter has shot a wolf."""
    state = state_of(
        (RoleName.WEREWOLF, True),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, True),
    )

    assert evaluate_victory(state) is None


def test_village_wins_when_the_last_wolf_dies_leaving_a_lone_villager() -> None:
    """First reference scenario of D-059, once the hunter has shot the last wolf."""
    state = state_of(
        (RoleName.WEREWOLF, False),
        (RoleName.VILLAGER, True),
        (RoleName.VILLAGER, False),
    )

    assert evaluate_victory(state) is Outcome.VILLAGE_WINS


def test_village_victory_takes_precedence_when_no_one_is_left() -> None:
    """Defensive: the engine must answer even for a state it should never reach."""
    state = state_of(
        (RoleName.WEREWOLF, False),
        (RoleName.VILLAGER, False),
    )

    assert evaluate_victory(state) is Outcome.VILLAGE_WINS
