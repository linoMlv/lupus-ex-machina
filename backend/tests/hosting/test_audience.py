"""Who a game is projected for (J8.3, D-100, D-105).

The recipient is derived from the state and nothing else — mode, seat and the
rule about the dead all travel in the rules the state carries (J6). A client
never asks for one: a spectator is omniscient, so a mode chosen per client would
let anybody open a second tab on a game they are playing, and the critical leak
test would stay green while protecting nothing.
"""

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameMode, GameRules, InformationOptions, TableOptions
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient
from lupus_ex_machina.hosting.audience import recipient_for

WATCHED = GameRules(table=TableOptions(player_count=6, seed=4))


def played_from(*, reveal_to_the_dead: bool = True) -> GameState:
    """A game of six the human sits at, seat zero."""
    return create_game(
        GameRules(
            table=TableOptions(player_count=6, seed=4, mode=GameMode.PLAYER, human_seat=0),
            information=InformationOptions(reveal_everything_to_the_dead=reveal_to_the_dead),
        ),
        rng=create_rng(4),
    )


def killed(state: GameState, player: PlayerId) -> GameState:
    return state.with_players_killed([player])


def test_a_watched_game_is_projected_for_the_spectator() -> None:
    assert recipient_for(create_game(WATCHED, rng=create_rng(4))) is SPECTATOR


def test_a_played_game_is_projected_for_the_seat_the_human_holds() -> None:
    state = played_from()

    assert recipient_for(state) == Recipient.of(state.players[0])


def test_the_dead_see_everything_once_their_character_is_gone() -> None:
    """The custom of Werewolf, and the reading of D-080 the owner already chose."""
    state = played_from()

    assert recipient_for(killed(state, state.players[0].id)) is SPECTATOR


def test_the_dead_may_be_kept_in_the_dark_when_the_rules_say_so() -> None:
    """The setting exists so the critical leak test can be played with it off."""
    state = played_from(reveal_to_the_dead=False)
    dead = killed(state, state.players[0].id)

    assert recipient_for(dead) == Recipient.of(state.players[0])


def test_another_player_dying_changes_nothing_for_the_human() -> None:
    """Guard against a rule that reads "somebody is dead" instead of "you are"."""
    state = played_from()

    assert recipient_for(killed(state, state.players[1].id)) == Recipient.of(state.players[0])
