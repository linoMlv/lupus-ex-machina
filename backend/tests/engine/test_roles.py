"""The registry of roles.

A role is declarative data the engine reads — its team, when it wakes, what it
may do, and what its death sets off (D-010). Nothing here is behaviour: the rules
that act on these declarations live in the validator and the night pipeline, so a
role stays a thing one can read in ten seconds.

The registry is checked for completeness rather than trusted: a role added
without a team, a wake order or an action set would fail at the far end of a
game, when it is asked to play.
"""

import pytest

from lupus_ex_machina.engine.roles import (
    ROLES,
    DeathTrigger,
    Role,
    RoleActionName,
    RoleName,
    Team,
    team_of,
)


def test_the_five_roles_of_v1_are_registered() -> None:
    """Villager, werewolf, seer, witch, hunter — and nothing else (D-015)."""
    assert set(ROLES) == {
        RoleName.VILLAGER,
        RoleName.WEREWOLF,
        RoleName.SEER,
        RoleName.WITCH,
        RoleName.HUNTER,
    }


def test_every_role_of_the_enum_has_an_entry() -> None:
    """Adding a role to the enum without registering it must fail here."""
    assert set(ROLES) == set(RoleName)


@pytest.mark.parametrize("name", list(RoleName))
def test_a_role_is_filed_under_its_own_name(name: RoleName) -> None:
    assert ROLES[name].name is name


@pytest.mark.parametrize(
    ("name", "team"),
    [
        (RoleName.VILLAGER, Team.VILLAGE),
        (RoleName.SEER, Team.VILLAGE),
        (RoleName.WITCH, Team.VILLAGE),
        (RoleName.HUNTER, Team.VILLAGE),
        (RoleName.WEREWOLF, Team.WEREWOLVES),
    ],
)
def test_every_role_wins_with_the_side_it_belongs_to(name: RoleName, team: Team) -> None:
    assert ROLES[name].team is team
    assert team_of(name) is team


# --- Waking order ------------------------------------------------------------


def test_the_seer_wakes_before_the_pack_and_the_witch_after_it() -> None:
    """The order is a rule, not a preference: the witch must see a designated victim.

    She learns whom the pack took (D-029), so she cannot be woken before it has
    chosen. The seer goes first, as at a real table.
    """
    order = [
        role.name
        for role in sorted(
            (role for role in ROLES.values() if role.wakes_at_night),
            key=lambda role: role.wake_order or 0,
        )
    ]

    assert order == [RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH]


@pytest.mark.parametrize("name", [RoleName.VILLAGER, RoleName.HUNTER])
def test_the_roles_with_nothing_to_do_at_night_are_never_woken(name: RoleName) -> None:
    """The hunter acts by day and in public, even when the night killed them (D-030)."""
    assert not ROLES[name].wakes_at_night
    assert ROLES[name].wake_order is None


def test_waking_is_read_off_the_order_rather_than_declared_twice() -> None:
    """One field, so the two cannot end up disagreeing."""
    for role in ROLES.values():
        assert role.wakes_at_night == (role.wake_order is not None)


def test_two_roles_never_share_a_wake_order() -> None:
    """A shared rank would make the order of the night depend on a dict."""
    ranks = [role.wake_order for role in ROLES.values() if role.wakes_at_night]

    assert len(ranks) == len(set(ranks))


# --- What each role may do ---------------------------------------------------


@pytest.mark.parametrize(
    ("name", "actions"),
    [
        (RoleName.VILLAGER, set()),
        (RoleName.WEREWOLF, {RoleActionName.DEVOUR}),
        (RoleName.SEER, {RoleActionName.INSPECT}),
        (RoleName.WITCH, {RoleActionName.HEAL, RoleActionName.POISON}),
        (RoleName.HUNTER, {RoleActionName.SHOOT}),
    ],
)
def test_every_role_declares_exactly_what_it_may_do(
    name: RoleName, actions: set[RoleActionName]
) -> None:
    assert ROLES[name].actions == actions


def test_a_role_that_wakes_has_something_to_do_there() -> None:
    for role in ROLES.values():
        if role.wakes_at_night:
            assert role.actions, f"{role.name} is woken for nothing"


def test_every_action_of_the_enum_belongs_to_a_role() -> None:
    """An action nobody can play is dead weight the validator would still carry."""
    declared = {action for role in ROLES.values() for action in role.actions}

    assert declared == set(RoleActionName)


# --- What a death sets off ---------------------------------------------------


def test_only_the_hunter_takes_someone_with_them() -> None:
    """The declarative form of D-010's `on_death`, without a callable in sight."""
    assert ROLES[RoleName.HUNTER].on_death is DeathTrigger.AVENGING_SHOT

    for role in ROLES.values():
        if role.name is not RoleName.HUNTER:
            assert role.on_death is None


def test_a_role_is_frozen() -> None:
    with pytest.raises(Exception, match="frozen"):
        ROLES[RoleName.VILLAGER].team = Team.WEREWOLVES


def test_a_role_can_be_declared_without_any_power() -> None:
    """The villager is the floor: a team, and nothing else."""
    plain = Role(name=RoleName.VILLAGER, team=Team.VILLAGE)

    assert not plain.wakes_at_night
    assert plain.actions == frozenset()
    assert plain.on_death is None
