"""Who may know what (D-009).

Visibility is the whole information model of the project: every configurable
option about information — revealing the role of the dead, a speaking seer, a
public vote history — is meant to become a change of visibility rather than a
condition scattered through the code. So the predicate itself must be airtight.

The spectator is a recipient like any other, not the absence of filtering: a
dedicated bypass is exactly where a leak would eventually hide.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.visibility import (
    SPECTATOR,
    Recipient,
    Visibility,
    VisibilityScope,
)

WOLF = Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF)
OTHER_WOLF = Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.WEREWOLF)
VILLAGER = Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER)


def every_visibility() -> list[Visibility]:
    return [
        Visibility.public(),
        Visibility.for_role(RoleName.WEREWOLF),
        Visibility.for_player(WOLF.id),
        Visibility.spectator_only(),
    ]


# --- The four scopes ---------------------------------------------------------


def test_a_public_fact_reaches_everyone() -> None:
    public = Visibility.public()

    assert public.reaches(Recipient.of(WOLF))
    assert public.reaches(Recipient.of(VILLAGER))


def test_a_role_fact_reaches_that_role_and_no_other() -> None:
    """The private channel of the pack: a villager must never see it."""
    pack = Visibility.for_role(RoleName.WEREWOLF)

    assert pack.reaches(Recipient.of(WOLF))
    assert pack.reaches(Recipient.of(OTHER_WOLF))
    assert not pack.reaches(Recipient.of(VILLAGER))


def test_a_player_fact_reaches_that_player_and_no_other() -> None:
    own = Visibility.for_player(WOLF.id)

    assert own.reaches(Recipient.of(WOLF))
    assert not own.reaches(Recipient.of(OTHER_WOLF)), "same role, still another player"
    assert not own.reaches(Recipient.of(VILLAGER))


def test_a_spectator_fact_reaches_no_player_at_all() -> None:
    """Rejected intents and inner thoughts are watched, never played against."""
    backstage = Visibility.spectator_only()

    assert not backstage.reaches(Recipient.of(WOLF))
    assert not backstage.reaches(Recipient.of(VILLAGER))


@pytest.mark.parametrize("visibility", every_visibility())
def test_the_spectator_sees_everything(visibility: Visibility) -> None:
    """Omniscience is a recipient the predicate accepts, not a code path."""
    assert visibility.reaches(SPECTATOR)


# --- A visibility cannot be malformed ----------------------------------------


def test_a_role_visibility_without_a_role_is_refused() -> None:
    with pytest.raises(ValidationError):
        Visibility(scope=VisibilityScope.ROLE)


def test_a_player_visibility_without_a_player_is_refused() -> None:
    with pytest.raises(ValidationError):
        Visibility(scope=VisibilityScope.PLAYER)


def test_a_public_visibility_carrying_an_audience_is_refused() -> None:
    """Silent contradictions are worse than errors: this one would leak."""
    with pytest.raises(ValidationError):
        Visibility(scope=VisibilityScope.PUBLIC, role=RoleName.WEREWOLF)


def test_a_spectator_visibility_carrying_an_audience_is_refused() -> None:
    with pytest.raises(ValidationError):
        Visibility(scope=VisibilityScope.SPECTATOR, player=WOLF.id)


def test_a_visibility_is_frozen() -> None:
    visibility = Visibility.public()

    with pytest.raises(ValidationError):
        visibility.scope = VisibilityScope.SPECTATOR


# --- Recipients --------------------------------------------------------------


def test_a_recipient_is_built_from_a_player_dead_or_alive() -> None:
    """The dead keep watching the game, so they keep receiving their own facts."""
    recipient = Recipient.of(WOLF.killed())

    assert recipient == Recipient.of(WOLF)
    assert Visibility.for_player(WOLF.id).reaches(recipient)


def test_a_half_declared_recipient_is_refused() -> None:
    """A recipient with an identity but no role would silently miss its own facts."""
    with pytest.raises(ValidationError):
        Recipient(player=WOLF.id)


def test_the_spectator_is_the_only_recipient_without_an_identity() -> None:
    assert SPECTATOR.is_spectator
    assert not Recipient.of(WOLF).is_spectator
