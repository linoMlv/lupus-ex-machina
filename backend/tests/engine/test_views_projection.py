"""What a player is shown of the game, and what is kept from them (D-009)."""

from lupus_ex_machina.engine.intents import (
    IntentKind,
    PriorityPoint,
)
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import NightOptions
from lupus_ex_machina.engine.views import project
from support.views_games import OTHER_VILLAGER, OTHER_WOLF, VILLAGER, WOLF, day, game, night

# --- What a player is shown of the game (D-009) ------------------------------


def test_a_view_never_carries_the_role_of_another_player() -> None:
    serialised = project(day(), VILLAGER).model_dump_json()

    assert RoleName.WEREWOLF.value not in serialised
    assert "Adèle" in serialised, "public identities are visible"


def test_an_agent_knows_its_own_role() -> None:
    assert project(day(), VILLAGER).role is RoleName.VILLAGER
    assert project(day(), WOLF).role is RoleName.WEREWOLF


def test_wolves_recognise_each_other_and_villagers_have_no_allies() -> None:
    """The pack meets on Night 0, without speaking (D-032)."""
    assert project(game(), WOLF).allies == (OTHER_WOLF,)
    assert project(game(), VILLAGER).allies == ()


def test_the_view_lists_who_is_still_alive() -> None:
    state = day().with_players_killed([OTHER_VILLAGER])

    view = project(state, VILLAGER)

    assert [player.id for player in view.players if player.alive] == [WOLF, OTHER_WOLF, VILLAGER]


def test_who_voted_is_public_but_never_for_whom() -> None:
    """Knowing who has voted is the pressure of the round; the target is not (D-013)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    view = project(state, VILLAGER)

    assert view.voters == (WOLF,)
    assert VILLAGER not in view.voters


def test_the_target_of_a_vote_never_reaches_anyone_elses_view() -> None:
    """Whom the wolf named is the one thing that differs between these two games.

    Comparing whole projections is what makes this falsifiable: any field that
    carried the target — under any name — would make the two views differ. Even
    the accused must not learn that they were named (D-013, GL-3).
    """
    against_villager = day().with_ballot_from(WOLF, VILLAGER)
    against_other = day().with_ballot_from(WOLF, OTHER_VILLAGER)

    for viewer in (VILLAGER, OTHER_VILLAGER, OTHER_WOLF):
        assert project(against_villager, viewer) == project(against_other, viewer)


def test_night_zero_offers_nothing_but_waiting() -> None:
    view = project(game(), WOLF)

    assert view.allowed_intents == (IntentKind.WAIT,)


def test_a_debate_day_offers_speaking_voting_and_waiting() -> None:
    view = project(day(), VILLAGER)

    assert set(view.allowed_intents) == {IntentKind.TAKE_TURN, IntentKind.WAIT}
    assert (view.may_speak, view.may_vote) == (True, True), "both halves of a turn are open"
    assert set(view.vote_targets) == {WOLF, OTHER_WOLF, OTHER_VILLAGER}
    assert VILLAGER not in view.vote_targets, "a player cannot vote for themselves"


def test_the_first_day_offers_no_target_at_all() -> None:
    view = project(day(number=1), VILLAGER)

    assert view.vote_targets == ()
    assert view.may_vote, "the blank vote stays available"


def test_a_player_who_voted_may_only_wait() -> None:
    state = day().with_ballot_from(VILLAGER, WOLF)

    view = project(state, VILLAGER)

    assert view.allowed_intents == (IntentKind.WAIT,)
    assert view.has_voted


def test_only_wolves_are_offered_the_night() -> None:
    """The pack alone designates; nobody speaks, and nobody votes (D-083)."""
    wolf = project(night(), WOLF)

    assert set(wolf.allowed_intents) == {IntentKind.SHARE_PRIORITY, IntentKind.WAIT}
    assert (wolf.may_speak, wolf.may_vote) == (False, False), "the night is silent"
    assert project(night(), VILLAGER).allowed_intents == (IntentKind.WAIT,)


def test_a_wolf_is_told_how_many_points_it_may_spread() -> None:
    """What a model needs to answer at all (D-008)."""
    assert project(night(), WOLF).priority_budget == NightOptions().priority_budget
    assert project(night(), VILLAGER).priority_budget == 0


def test_a_wolf_is_never_offered_its_own_pack_as_prey() -> None:
    view = project(night(), WOLF)

    assert set(view.action_targets) == {VILLAGER, OTHER_VILLAGER}


def test_a_wolf_that_already_spread_its_points_has_nothing_left_to_do() -> None:
    """One gesture a night, and his was the spread (D-006)."""
    state = night().with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=50),))

    view = project(state, WOLF)

    assert view.allowed_intents == (IntentKind.WAIT,)
    assert (view.may_speak, view.may_vote) == (False, False)
    assert view.action_targets == ()
    assert view.priority_budget == 0
