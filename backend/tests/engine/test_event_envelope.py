"""The envelope: where a fact sits in the game, and what it derives (D-040)."""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    Event,
    EventPayload,
    RoleAssigned,
    SpeechDelivered,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.visibility import SPECTATOR, Visibility
from support.facts import WHEN, WOLF

# --- The envelope ------------------------------------------------------------


def event(payload: EventPayload, *, sequence: int = 0) -> Event:
    return Event(
        sequence=sequence,
        recorded_at=WHEN,
        phase=Phase.DAY,
        day=2,
        payload=payload,
    )


def test_an_event_carries_when_and_where_it_happened() -> None:
    recorded = event(SpeechDelivered(speaker=WOLF, speech="Bonsoir."), sequence=7)

    assert recorded.sequence == 7
    assert recorded.recorded_at == WHEN
    assert recorded.phase is Phase.DAY
    assert recorded.day == 2


def test_an_event_takes_its_visibility_from_its_payload() -> None:
    """One source of truth: an envelope that could disagree would be believed."""
    recorded = event(RoleAssigned(player=WOLF, role=RoleName.WEREWOLF))

    assert recorded.visibility == Visibility.for_player(WOLF)
    assert recorded.is_visible_to(SPECTATOR)


def test_an_event_is_frozen() -> None:
    recorded = event(BallotAnnounced(voter=WOLF))

    with pytest.raises(ValidationError):
        recorded.sequence = 3


def test_an_event_survives_a_round_trip_through_json() -> None:
    """The journal is written as JSON lines, so this is the persistence contract."""
    recorded = event(SpeechDelivered(speaker=WOLF, speech="Théo, tu mens — j'en suis sûre."))

    assert Event.model_validate_json(recorded.model_dump_json()) == recorded


def test_the_serialised_form_states_the_audience() -> None:
    """Written out for the reader of a journal file, derived so it cannot lie."""
    dumped = event(RoleAssigned(player=WOLF, role=RoleName.WEREWOLF)).model_dump()

    assert dumped["visibility"] == Visibility.for_player(WOLF).model_dump()
