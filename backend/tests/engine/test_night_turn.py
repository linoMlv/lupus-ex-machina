"""The turn each player takes at night (D-083, D-084, D-085).

The night is not a conversation. Nobody speaks — the pack included, as at a real
table where the wolves designate their prey in silence. What a player does with
their turn is read their notebook, think it over privately, and decide; the
first two belong to J7, and what the engine owes them is the turn itself.

Two consequences the engine has to carry, and they are what this file holds:
every living player is called, whether or not they hold a power, and a wolf
spreads its points without seeing what the others spread. The pack is shown the
detail once its prey is settled, which is the night's counterpart to the count
of the day (D-082).
"""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import PrioritiesRevealed, PriorityShared, RevealedShare
from lupus_ex_machina.engine.intents import PriorityPoint, TakeTurn
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.night import night_callers
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import GameRules, InformationOptions
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.visibility import Recipient

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
SEER = PlayerId("p2")
WITCH = PlayerId("p3")
HUNTER = PlayerId("p4")
VILLAGER = PlayerId("p5")

TABLE = (
    Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=WITCH, name="Diane", seat=3, role=RoleName.WITCH),
    Player(id=HUNTER, name="Émile", seat=4, role=RoleName.HUNTER),
    Player(id=VILLAGER, name="Faustine", seat=5, role=RoleName.VILLAGER),
)


def night(rules: GameRules | None = None) -> GameState:
    return (
        GameState.initial(TABLE, rules=rules)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


def as_wolf(of: PlayerId = WOLF) -> Recipient:
    return Recipient(player=of, role=RoleName.WEREWOLF)


# --- Nobody speaks at night (D-083, revokes D-007) ---------------------------


def test_a_wolf_may_not_speak_at_night() -> None:
    """The pack designates in silence, as at a real table.

    D-007 gave the wolves a channel of their own; playing it out showed what it
    cost — a wolf gets one gesture a night, so speaking meant giving up any say
    in the prey. The silence is the rule now.
    """
    with pytest.raises(IllegalIntentError, match="only allowed during the day"):
        validate_intent(night(), WOLF, TakeTurn(speech="On prend Camille."))


def test_no_role_at_all_speaks_at_night() -> None:
    for player in (SEER, WITCH, VILLAGER):
        with pytest.raises(IllegalIntentError):
            validate_intent(night(), player, TakeTurn(speech="J'ai une idée."))


# --- Every living player has a turn (D-084) ----------------------------------


def test_the_night_calls_every_living_player() -> None:
    """Even those with nothing to do: a turn is a notebook read and a thought.

    The villager acts on none of it, and that is the point — his turn exists so
    that his deductions keep up with the game rather than restarting each dawn.
    """
    called = [player.id for player in night_callers(night())]

    assert set(called) == {WOLF, OTHER_WOLF, SEER, WITCH, HUNTER, VILLAGER}


def test_the_roles_with_a_power_are_called_first_and_in_order() -> None:
    """The wake order is a rule (D-029); the rest is a stable sweep by seat."""
    called = [player.id for player in night_callers(night())]

    assert called == [SEER, WOLF, OTHER_WOLF, WITCH, HUNTER, VILLAGER]


def test_the_night_still_never_calls_the_dead() -> None:
    state = night().with_players_killed([VILLAGER, SEER])

    called = {player.id for player in night_callers(state)}

    assert called == {WOLF, OTHER_WOLF, WITCH, HUNTER}


def test_an_empty_handed_witch_is_called_like_anybody_else() -> None:
    """D-054 has no object left: she is called because everyone is (D-084)."""
    state = (
        night()
        .with_power_spent_by(WITCH, RoleActionName.HEAL)
        .with_power_spent_by(WITCH, RoleActionName.POISON)
    )

    assert WITCH in {player.id for player in night_callers(state)}


# --- The pack spreads its points blind (D-085) -------------------------------


def shared(state: GameState, actor: PlayerId, target: PlayerId) -> GameState:
    return state.with_priority_share_from(actor, (PriorityPoint(target=target, points=100),))


def test_a_wolf_never_sees_what_another_wolf_put_where() -> None:
    """Blind, so the pack cannot follow its first speaker into a herd vote."""
    journal = Journal()
    state = night()
    journal.record(PriorityShared(actor=OTHER_WOLF, allocations=()), at=state)

    seen = project_journal(journal.events, as_wolf(WOLF))

    assert seen == (), "another wolf's spread is his own until the designation"


def test_a_wolf_still_sees_his_own_spread() -> None:
    """It is his: he has to be able to read back what he did."""
    journal = Journal()
    journal.record(PriorityShared(actor=WOLF, allocations=()), at=night())

    assert len(project_journal(journal.events, as_wolf(WOLF))) == 1


# --- And is shown the detail once the prey is settled (D-085) ----------------


def test_the_pack_is_shown_who_weighed_what_once_it_has_settled() -> None:
    """The night's counterpart to the count of the day (D-082).

    Revealed after the fact rather than during: what makes the spread blind is
    that it cannot be answered, not that it stays secret forever.
    """
    revealed = PrioritiesRevealed(shares=(RevealedShare(wolf=WOLF, allocations=()),))

    assert revealed.audience.reaches(as_wolf(OTHER_WOLF))
    assert not revealed.audience.reaches(Recipient(player=SEER, role=RoleName.SEER))


def test_a_table_may_keep_the_spreads_to_themselves() -> None:
    """Configurable, and the option decides whether the fact exists at all."""
    assert InformationOptions().reveal_priorities_at_the_designation is True
    assert (
        InformationOptions(
            reveal_priorities_at_the_designation=False
        ).reveal_priorities_at_the_designation
        is False
    )


def test_a_settled_night_reveals_every_spread_it_collected() -> None:
    """Played end to end: the fact carries what each wolf actually put down."""
    from lupus_ex_machina.engine.runner import _Run

    state = shared(shared(night(), WOLF, VILLAGER), OTHER_WOLF, VILLAGER)
    journal = Journal()
    run = _Run({}, journal, create_rng(1))

    run._reveal_what_the_pack_weighed(state)

    (fact,) = [
        event.payload for event in journal.events if isinstance(event.payload, PrioritiesRevealed)
    ]
    assert {share.wolf for share in fact.shares} == {WOLF, OTHER_WOLF}


def test_a_pack_kept_in_the_dark_is_shown_nothing_at_all() -> None:
    """The other half of the option, so neither branch goes untested."""
    from lupus_ex_machina.engine.runner import _Run

    discreet = GameRules(information=InformationOptions(reveal_priorities_at_the_designation=False))
    state = shared(night(discreet), WOLF, VILLAGER)
    journal = Journal()

    _Run({}, journal, create_rng(1))._reveal_what_the_pack_weighed(state)

    assert journal.events == ()
