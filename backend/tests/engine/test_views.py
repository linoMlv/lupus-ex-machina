"""What an agent is allowed to see.

An agent never receives the state, only a projection of it (D-001). J3 turns
this into the general visibility model; what matters already is the boundary:
the role of another player must not appear anywhere in the view (GL-3).
"""

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import NightOptions
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
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
    """The pack keeps its own floor and its own vote; nobody else has either."""
    wolf = project(night(), WOLF)

    assert set(wolf.allowed_intents) == {
        IntentKind.TAKE_TURN,
        IntentKind.SHARE_PRIORITY,
        IntentKind.WAIT,
    }
    assert (wolf.may_speak, wolf.may_vote) == (True, False), "the pack talks, it does not vote"
    assert project(night(), VILLAGER).allowed_intents == (IntentKind.WAIT,)


def test_a_wolf_is_told_how_many_points_it_may_spread() -> None:
    """What a model needs to answer at all (D-008)."""
    assert project(night(), WOLF).priority_budget == NightOptions().priority_budget
    assert project(night(), VILLAGER).priority_budget == 0


def test_a_wolf_is_never_offered_its_own_pack_as_prey() -> None:
    view = project(night(), WOLF)

    assert set(view.action_targets) == {VILLAGER, OTHER_VILLAGER}


def test_a_wolf_that_already_spread_its_points_keeps_only_the_floor() -> None:
    state = night().with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=50),))

    view = project(state, WOLF)

    assert set(view.allowed_intents) == {IntentKind.TAKE_TURN, IntentKind.WAIT}
    assert (view.may_speak, view.may_vote) == (True, False)
    assert view.action_targets == ()
    assert view.priority_budget == 0


# --- The view and the validator must tell the same story ---------------------


def accepts(state: GameState, actor: PlayerId, intent: Intent) -> bool:
    """Whether the validator would let this actor play this intent."""
    try:
        validate_intent(state, actor, intent)
    except IllegalIntentError:
        return False
    return True


def every_moment_of_a_game() -> list[GameState]:
    """One state per moment a view can be built from, including the closed ones."""
    a_share = (PriorityPoint(target=VILLAGER, points=50),)
    return [
        game(),
        day(number=1),
        day(),
        day().with_ballot_from(WOLF, VILLAGER),
        day().with_players_killed([VILLAGER]),
        day().reopened_for_runoff((WOLF, VILLAGER)),
        night(),
        night().with_priority_share_from(WOLF, a_share),
        night().with_players_killed([VILLAGER]),
        night().reopened_for_runoff((VILLAGER,)),
        day().entering(Phase.RESOLUTION),
        day().entering(Phase.RESOLUTION).entering(Phase.ENDED),
    ]


def test_the_view_offers_exactly_the_targets_the_validator_accepts() -> None:
    """The view is a promise, and the validator is the one that keeps it.

    A target offered but refused strands an agent on a move it was invited to
    play; a target refused but offered hands it a move the rules say does not
    exist. Both are silent until a model meets them (J7), so the two are compared
    exhaustively here, for every player — dead ones included — at every moment.
    """
    for state in every_moment_of_a_game():
        for actor in state.players:
            view = project(state, actor.id)

            for other in state.players:
                where = f"{state.phase} day {state.day}: {actor.id} -> {other.id}"
                assert (other.id in view.vote_targets) == accepts(
                    state, actor.id, TakeTurn(vote=Vote(target=other.id))
                ), f"vote, {where}"
                assert (other.id in view.action_targets) == accepts(
                    state,
                    actor.id,
                    SharePriority(allocations=(PriorityPoint(target=other.id, points=10),)),
                ), f"prey, {where}"


def test_the_view_offers_exactly_the_intent_kinds_the_validator_accepts() -> None:
    """Same promise, on the moves that need no target.

    SHARE_PRIORITY always needs one, so it is covered by the test above.
    """
    speaking = TakeTurn(speech="Je vous écoute.")
    voting = TakeTurn(vote=Vote())

    for state in every_moment_of_a_game():
        for actor in state.players:
            view = project(state, actor.id)
            where = f"at {state.phase} day {state.day}, for {actor.id}"

            may_speak = accepts(state, actor.id, speaking)
            may_vote = accepts(state, actor.id, voting)

            assert view.may_speak == may_speak, f"speaking {where}"
            assert view.may_vote == may_vote, f"voting {where}"
            assert (IntentKind.WAIT in view.allowed_intents) == accepts(state, actor.id, Wait()), (
                f"waiting {where}"
            )
            assert (IntentKind.TAKE_TURN in view.allowed_intents) == (may_speak or may_vote), (
                f"taking a turn {where}"
            )


# --- The witch is told whom to save, and she alone ---------------------------


def a_night_where_the_pack_took_the_villager() -> GameState:
    """A night the pack has settled, on a table that holds a witch."""
    table = (
        Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
        Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WITCH),
        Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
        Player(id=OTHER_VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
    )
    return (
        GameState.initial(table)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
        .with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=100),))
    )


def test_the_witch_is_told_whom_the_pack_took() -> None:
    """Her potion saves that one player and no other (D-029).

    Without this she is handed a power and no way to aim it: the view offers the
    union of what both her potions reach, which does not say which is which.
    """
    witch = OTHER_WOLF  # seated as the witch on this table

    assert project(a_night_where_the_pack_took_the_villager(), witch).victim_tonight == VILLAGER


def test_nobody_but_the_witch_is_told_whom_the_pack_took() -> None:
    """It is the pack's secret until dawn, and hers only because she answers it."""
    state = a_night_where_the_pack_took_the_villager()

    for viewer in (WOLF, VILLAGER, OTHER_VILLAGER):
        assert project(state, viewer).victim_tonight is None, viewer


def test_a_witch_out_of_life_potions_is_told_nothing() -> None:
    """Shown exactly while she can act on it, which is what the validator asks too."""
    state = a_night_where_the_pack_took_the_villager().with_power_spent_by(
        OTHER_WOLF, RoleActionName.HEAL
    )

    assert project(state, OTHER_WOLF).victim_tonight is None
