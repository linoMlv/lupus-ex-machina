"""What an agent is allowed to see.

An agent never receives the state, only a projection of it (D-001). J3 turns
this into the general visibility model; what matters already is the boundary:
the role of another player must not appear anywhere in the view (GL-3).
"""

from lupus_ex_machina.engine.intents import IntentKind
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER_VILLAGER = PlayerId("p3")


def game() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
            Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
        )
    )


def day(number: int = 2) -> GameState:
    return game().entering(Phase.DAY, day=number)


def night() -> GameState:
    return day().entering(Phase.RESOLUTION).entering(Phase.NIGHT)


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
    assert "ballots" not in view.model_dump(), "ballots themselves never reach a view"
    assert all(isinstance(voter, str) for voter in view.voters), "a voter carries no target"


def test_night_zero_offers_nothing_but_waiting() -> None:
    view = project(game(), WOLF)

    assert view.allowed_intents == (IntentKind.WAIT,)


def test_a_debate_day_offers_speaking_voting_and_waiting() -> None:
    view = project(day(), VILLAGER)

    assert set(view.allowed_intents) == {IntentKind.SPEAK, IntentKind.VOTE, IntentKind.WAIT}
    assert set(view.vote_targets) == {WOLF, OTHER_WOLF, OTHER_VILLAGER}
    assert VILLAGER not in view.vote_targets, "a player cannot vote for themselves"


def test_the_first_day_offers_no_target_at_all() -> None:
    view = project(day(number=1), VILLAGER)

    assert view.vote_targets == ()
    assert IntentKind.VOTE in view.allowed_intents, "the blank vote stays available"


def test_a_player_who_voted_may_only_wait() -> None:
    state = day().with_ballot_from(VILLAGER, WOLF)

    view = project(state, VILLAGER)

    assert view.allowed_intents == (IntentKind.WAIT,)
    assert view.has_voted


def test_only_wolves_are_offered_a_night_action() -> None:
    assert project(night(), WOLF).allowed_intents == (IntentKind.ROLE_ACTION, IntentKind.WAIT)
    assert project(night(), VILLAGER).allowed_intents == (IntentKind.WAIT,)


def test_a_wolf_is_never_offered_its_own_pack_as_prey() -> None:
    view = project(night(), WOLF)

    assert set(view.night_targets) == {VILLAGER, OTHER_VILLAGER}


def test_a_wolf_that_already_chose_may_only_wait() -> None:
    state = night().with_night_choice_from(WOLF, VILLAGER)

    assert project(state, WOLF).allowed_intents == (IntentKind.WAIT,)
