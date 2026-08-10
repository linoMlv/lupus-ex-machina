"""How far ahead of its audience a hosted game runs (J8.4, D-014, D-023).

Two settings, and the difference between them is the whole of D-014. A watched
game may run a few turns ahead, because the display is what hides the latency of
the models. A **played** game may not: one turn in flight means the button of an
absolute priority is always read before the next turn is played, so there is
never a pre-computed turn to throw away — and nothing is ever removed from a
journal that does not allow it (D-040).
"""

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.rules import GameMode, GameRules, NightOptions, TableOptions
from lupus_ex_machina.hosting.lead import turns_of_lead

WATCHED = GameRules(table=TableOptions(player_count=6, seed=4))
PLAYED = GameRules(table=TableOptions(player_count=6, seed=4, mode=GameMode.PLAYER, human_seat=0))


def test_a_watched_game_may_run_a_few_turns_ahead() -> None:
    """The display is what hides the latency of the models (D-023)."""
    assert turns_of_lead(GameConfiguration(rules=WATCHED)) > 1


def test_a_played_game_runs_exactly_one_turn_at_a_time() -> None:
    """So an absolute priority is always read before the next turn (D-014).

    The one that makes "the pre-computed turn is thrown away" unnecessary: there
    is never one to throw, and a fact is never removed from the journal.
    """
    assert turns_of_lead(GameConfiguration(rules=PLAYED)) == 1


def test_the_lead_is_never_nothing() -> None:
    """A game allowed no turn in flight would never play its first one."""
    every_mode = (WATCHED, PLAYED, GameRules(night=NightOptions(require_werewolf_target=True)))

    assert all(turns_of_lead(GameConfiguration(rules=rules)) >= 1 for rules in every_mode)
