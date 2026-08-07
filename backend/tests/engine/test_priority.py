"""How the pack picks its prey (D-008).

Each wolf spreads a fixed budget of points over the prey it would rather take,
negative points included. The amendment matters: with a free score, a wolf that
puts the maximum everywhere drowns out the others, and the system would reward
vehemence rather than conviction. A budget forces a real trade-off and makes two
wolves' preferences comparable.

The tally is pure. Who is asked, and whether they are asked twice, belongs to the
night; what a set of answers adds up to belongs here.
"""

import pytest

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.priority import Tally, tally
from lupus_ex_machina.engine.records import PriorityShare

WOLF = PlayerId("w0")
OTHER_WOLF = PlayerId("w1")
ANNE = PlayerId("p2")
BRUNO = PlayerId("p3")
CLARA = PlayerId("p4")


def share(actor: PlayerId, **points: int) -> PriorityShare:
    """One wolf's spread, written as ``share(WOLF, p2=60, p3=-10)``."""
    return PriorityShare(
        actor=actor,
        allocations=tuple(
            PriorityPoint(target=PlayerId(target), points=amount)
            for target, amount in points.items()
        ),
    )


# --- Adding up ---------------------------------------------------------------


def test_a_lone_wolf_takes_the_prey_it_named() -> None:
    assert tally([share(WOLF, p2=100)]).designated == ANNE


def test_two_wolves_agreeing_carry_their_prey() -> None:
    counted = tally([share(WOLF, p2=60, p3=40), share(OTHER_WOLF, p2=70, p3=30)])

    assert counted.designated == ANNE


def test_the_totals_of_every_wolf_are_added_together() -> None:
    counted = tally([share(WOLF, p2=30, p3=50), share(OTHER_WOLF, p2=40, p3=10)])

    assert counted.total_for(ANNE) == 70
    assert counted.total_for(BRUNO) == 60
    assert counted.designated == ANNE


def test_a_target_nobody_named_counts_for_nothing() -> None:
    assert tally([share(WOLF, p2=10)]).total_for(CLARA) == 0


def test_negative_points_push_a_target_away() -> None:
    """« Surtout pas lui, il me couvre » — the whole point of allowing them."""
    counted = tally([share(WOLF, p2=50, p3=30), share(OTHER_WOLF, p2=-60, p3=10)])

    assert counted.total_for(ANNE) == -10
    assert counted.designated == BRUNO


def test_a_wolf_can_veto_a_prey_the_others_wanted() -> None:
    counted = tally([share(WOLF, p2=40), share(OTHER_WOLF, p2=-40, p3=10)])

    assert counted.total_for(ANNE) == 0
    assert counted.designated == BRUNO


# --- When nobody is designated -----------------------------------------------


def test_an_empty_tally_designates_nobody() -> None:
    assert tally([]).designated is None
    assert tally([]).leaders == ()


def test_a_tie_designates_nobody() -> None:
    """A tie spares everyone, here as at the day vote (D-050)."""
    counted = tally([share(WOLF, p2=50, p3=50)])

    assert counted.designated is None
    assert set(counted.leaders) == {ANNE, BRUNO}


def test_a_tie_between_three_designates_nobody() -> None:
    counted = tally([share(WOLF, p2=20, p3=20, p4=20)])

    assert counted.designated is None
    assert len(counted.leaders) == 3


def test_a_pack_that_wants_nobody_dead_designates_nobody() -> None:
    """A total has to be positive to count as wanting someone taken.

    Points cancelling out, or nothing but aversion, is a pack that did not pick a
    prey — not a pack whose least-hated member dies.
    """
    assert tally([share(WOLF, p2=0, p3=0)]).designated is None
    assert tally([share(WOLF, p2=-10, p3=-50)]).designated is None
    assert tally([share(WOLF, p2=40), share(OTHER_WOLF, p2=-40)]).designated is None


def test_the_leaders_of_a_pack_that_wants_nobody_are_empty() -> None:
    """Nothing to run off against, which the runoff relies on."""
    assert tally([share(WOLF, p2=-10, p3=-10)]).leaders == ()


# --- Reading a tally ---------------------------------------------------------


def test_a_tally_is_ordered_from_the_most_wanted_down() -> None:
    counted = tally([share(WOLF, p2=10, p3=70, p4=40)])

    assert [entry.target for entry in counted.totals] == [BRUNO, CLARA, ANNE]


def test_a_tally_is_frozen() -> None:
    counted = tally([share(WOLF, p2=10)])

    with pytest.raises(Exception, match="frozen"):
        counted.totals = ()


def test_a_tally_holds_one_entry_per_named_target() -> None:
    counted = tally([share(WOLF, p2=10, p3=20), share(OTHER_WOLF, p2=5)])

    assert len(counted.totals) == 2


def test_an_empty_tally_is_still_a_tally() -> None:
    assert isinstance(tally([]), Tally)
    assert tally([]).total_for(ANNE) == 0
