"""The journal, and what each recipient is allowed to read of it.

The journal is the source of truth of a game (D-040): append-only, so a fact can
be added but never rewritten, and projected per recipient so the filtering
happens at the source rather than at the display (D-046).
"""

from datetime import UTC, datetime, timedelta

import pytest

from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    Event,
    IntentRejected,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    PriorityShared,
    RoleAssigned,
    SpeechDelivered,
)
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient

WOLF = Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF)
OTHER_WOLF = Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.WEREWOLF)
VILLAGER = Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER)

START = datetime(2026, 8, 3, 21, 0, tzinfo=UTC)


def game() -> GameState:
    return GameState.initial((WOLF, OTHER_WOLF, VILLAGER))


class SteadyClock:
    """A clock advancing one second per reading, so timestamps stay predictable."""

    def __init__(self) -> None:
        """Start at a fixed instant."""
        self._readings = 0

    def __call__(self) -> datetime:
        """Return the next instant."""
        instant = START + timedelta(seconds=self._readings)
        self._readings += 1
        return instant


def journal() -> Journal:
    return Journal(clock=SteadyClock())


# --- Append-only -------------------------------------------------------------


def test_a_new_journal_holds_nothing() -> None:
    assert journal().events == ()


def test_recording_appends_in_order() -> None:
    recorder, state = journal(), game()

    recorder.record(PlayerSeated(player=WOLF.id, name=WOLF.name, seat=0), at=state)
    recorder.record(PlayerSeated(player=VILLAGER.id, name=VILLAGER.name, seat=2), at=state)

    assert [event.sequence for event in recorder.events] == [0, 1]
    assert [event.payload.seat for event in recorder.events] == [0, 2]  # type: ignore[union-attr]


def test_an_event_is_stamped_with_the_moment_and_the_phase_it_happened_in() -> None:
    """Taking the phase from the state removes any chance of recording a wrong one."""
    recorder = journal()
    state = game().entering(Phase.DAY, day=3)

    recorded = recorder.record(SpeechDelivered(speaker=WOLF.id, speech="Bonsoir."), at=state)

    assert recorded.recorded_at == START
    assert recorded.phase is Phase.DAY
    assert recorded.day == 3


def test_the_clock_advances_with_the_game() -> None:
    recorder, state = journal(), game()

    first = recorder.record(BallotAnnounced(voter=WOLF.id), at=state)
    second = recorder.record(BallotAnnounced(voter=VILLAGER.id), at=state)

    assert second.recorded_at > first.recorded_at


def test_a_journal_hands_out_a_snapshot_it_cannot_be_edited_through() -> None:
    """A correction is a new fact, never a rewrite of an old one."""
    recorder, state = journal(), game()
    recorder.record(BallotAnnounced(voter=WOLF.id), at=state)

    events = recorder.events
    recorder.record(BallotAnnounced(voter=VILLAGER.id), at=state)

    assert len(events) == 1, "the snapshot taken earlier did not change"
    assert len(recorder.events) == 2
    assert isinstance(events, tuple), "there is nothing to mutate in the first place"


def test_a_journal_counts_what_it_holds() -> None:
    recorder, state = journal(), game()
    recorder.record(BallotAnnounced(voter=WOLF.id), at=state)

    assert len(recorder) == 1


# --- Projection --------------------------------------------------------------


def populated() -> Journal:
    """A journal holding one fact of each audience."""
    recorder, state = journal(), game()

    recorder.record(PhaseEntered(phase=Phase.NIGHT_ZERO, day=0), at=state)
    recorder.record(RoleAssigned(player=WOLF.id, role=RoleName.WEREWOLF), at=state)
    recorder.record(PackRevealed(members=(WOLF.id, OTHER_WOLF.id)), at=state)
    recorder.record(
        PriorityShared(actor=WOLF.id, allocations=(PriorityPoint(target=VILLAGER.id, points=60),)),
        at=state,
    )
    recorder.record(BallotCast(voter=VILLAGER.id, target=WOLF.id), at=state)
    recorder.record(IntentRejected(actor=VILLAGER.id, reason="already voted"), at=state)
    return recorder


def kinds_seen_by(recipient: Recipient) -> list[str]:
    return [event.payload.kind for event in project_journal(populated().events, recipient)]


def test_a_villager_never_sees_the_channel_of_the_pack() -> None:
    """The reason the visibility model exists at all (D-007, D-009)."""
    seen = kinds_seen_by(Recipient.of(VILLAGER))

    assert "pack_revealed" not in seen
    assert "priority_shared" not in seen
    assert "phase_entered" in seen, "public facts still get through"


def test_a_wolf_knows_its_own_pack() -> None:
    assert "pack_revealed" in kinds_seen_by(Recipient.of(OTHER_WOLF))


def test_a_wolf_does_not_see_what_another_wolf_weighed() -> None:
    """The pack designates blind (D-085); the detail comes after the fact."""
    assert "priority_shared" in kinds_seen_by(Recipient.of(WOLF)), "one reads one's own"
    assert "priority_shared" not in kinds_seen_by(Recipient.of(OTHER_WOLF))


def test_nobody_at_the_table_sees_another_players_role() -> None:
    assert "role_assigned" not in kinds_seen_by(Recipient.of(VILLAGER))
    assert "role_assigned" not in kinds_seen_by(Recipient.of(OTHER_WOLF))
    assert "role_assigned" in kinds_seen_by(Recipient.of(WOLF)), "one knows one's own role"


def test_nobody_at_the_table_sees_a_rejected_intent() -> None:
    """Not even its author: fumbling is between the engine and the audience."""
    for player in (WOLF, OTHER_WOLF, VILLAGER):
        assert "intent_rejected" not in kinds_seen_by(Recipient.of(player))


def test_the_spectator_reads_the_journal_whole() -> None:
    assert len(project_journal(populated().events, SPECTATOR)) == len(populated().events)


def test_a_projection_keeps_the_order_of_the_journal() -> None:
    """A filtered journal is still a story, told in the order it happened."""
    seen = project_journal(populated().events, Recipient.of(WOLF))

    assert [event.sequence for event in seen] == sorted(event.sequence for event in seen)


def test_a_projection_never_renumbers_what_it_keeps() -> None:
    """Sequence numbers are the identity of a fact, not a position in a list.

    Renumbering would let a recipient tell how many facts were hidden from them
    — and, over a night, which roles are still in play.
    """
    seen = project_journal(populated().events, Recipient.of(VILLAGER))
    whole = populated().events

    assert [event.sequence for event in seen] == [
        event.sequence for event in whole if event.is_visible_to(Recipient.of(VILLAGER))
    ]
    assert seen[0].sequence == 0


def test_projecting_works_on_any_run_of_events_not_just_a_journal() -> None:
    """The same filter serves a file read back from disk, and the socket in J8."""
    events: list[Event] = list(populated().events)

    assert project_journal(events, SPECTATOR) == tuple(events)


@pytest.mark.parametrize("player", [WOLF, OTHER_WOLF, VILLAGER])
def test_the_dead_keep_reading_what_was_always_theirs(player: Player) -> None:
    alive = project_journal(populated().events, Recipient.of(player))
    dead = project_journal(populated().events, Recipient.of(player.killed()))

    assert alive == dead
