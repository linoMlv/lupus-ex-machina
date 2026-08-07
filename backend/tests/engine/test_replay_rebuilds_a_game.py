"""A game is rebuilt from its journal alone (D-040)."""

from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    GameEnded,
    IntentRejected,
    NightResolved,
    NotebookEntryRecorded,
    PriorityShared,
    PrivateReasoningRecorded,
    RoleRevealed,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.records import Speech
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome
from support.recorders import TABLE, VILLAGER, WOLF, Recorder

# --- A game is rebuilt from its journal alone (D-040) ------------------------


def test_a_journal_of_a_freshly_dealt_game_rebuilds_the_opening_state() -> None:
    rebuilt = replay(Recorder().journal.events)

    assert rebuilt == GameState.initial(TABLE)


def test_replay_restores_the_roles_the_table_never_saw() -> None:
    """Roles are private facts, and the state cannot be rebuilt without them."""
    rebuilt = replay(Recorder().journal.events)

    assert rebuilt.player(WOLF.id).role is RoleName.WEREWOLF
    assert rebuilt.player(VILLAGER.id).role is RoleName.VILLAGER


def test_replay_restores_the_ballots_of_the_round() -> None:
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(BallotCast(voter=VILLAGER.id, target=WOLF.id))
    recorder.write(BallotAnnounced(voter=VILLAGER.id))
    recorder.write(BallotCast(voter=WOLF.id, target=None))

    rebuilt = replay(recorder.journal.events)

    assert [(ballot.voter, ballot.target) for ballot in rebuilt.ballots] == [
        (VILLAGER.id, WOLF.id),
        (WOLF.id, None),
    ]


def test_replay_restores_what_the_pack_designated() -> None:
    recorder = Recorder().enter(Phase.DAY, day=1).enter(Phase.RESOLUTION).enter(Phase.NIGHT)
    recorder.write(
        PriorityShared(actor=WOLF.id, allocations=(PriorityPoint(target=VILLAGER.id, points=60),))
    )

    rebuilt = replay(recorder.journal.events)

    assert rebuilt.has_acted_tonight(WOLF.id)


def test_a_resolved_vote_kills_and_closes_the_round() -> None:
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(BallotCast(voter=VILLAGER.id, target=WOLF.id))
    recorder.enter(Phase.RESOLUTION).write(VoteResolved(eliminated=WOLF.id))

    rebuilt = replay(recorder.journal.events)

    assert not rebuilt.is_alive(WOLF.id)
    assert rebuilt.ballots == (), "a resolved round carries no ballot over"


def test_a_resolved_night_kills_its_victim() -> None:
    recorder = Recorder().enter(Phase.DAY, day=1).enter(Phase.RESOLUTION).enter(Phase.NIGHT)
    recorder.write(
        PriorityShared(actor=WOLF.id, allocations=(PriorityPoint(target=VILLAGER.id, points=60),))
    )
    recorder.enter(Phase.RESOLUTION).write(NightResolved(victims=(VILLAGER.id,)))

    rebuilt = replay(recorder.journal.events)

    assert not rebuilt.is_alive(VILLAGER.id)
    assert rebuilt.priority_shares == ()


def test_a_tie_that_spared_everyone_replays_as_such() -> None:
    """A resolution without a victim is a fact of its own (D-050)."""
    recorder = Recorder().enter(Phase.DAY, day=2).enter(Phase.RESOLUTION)
    recorder.write(VoteResolved(eliminated=None))

    rebuilt = replay(recorder.journal.events)

    assert len(rebuilt.living) == len(TABLE)


def test_a_replayed_turn_at_the_floor_is_given_back_to_the_round() -> None:
    """A replayed round gets its turns at the floor back.

    The auction is scored against them (D-002). Rebuilt without them, a game
    would arbitrate differently from the one it claims to be replaying.
    """
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(
        SpeechDelivered(
            speaker=WOLF.id, speech="Camille, tu mens.", addressed=VILLAGER.id, accused=VILLAGER.id
        )
    )

    rebuilt = replay(recorder.journal.events)

    assert rebuilt.floor == (
        Speech(speaker=WOLF.id, words=3, addressed=VILLAGER.id, accused=VILLAGER.id),
    )


def test_facts_that_change_nothing_leave_the_state_alone() -> None:
    """Thoughts and announcements are information, not effects."""
    recorder = Recorder().enter(Phase.DAY, day=2)
    plain = replay(recorder.journal.events)

    recorder.write(BallotAnnounced(voter=WOLF.id))
    recorder.write(RoleRevealed(player=VILLAGER.id, role=RoleName.VILLAGER))
    recorder.write(IntentRejected(actor=WOLF.id, reason="already voted"))
    recorder.write(PrivateReasoningRecorded(player=WOLF.id, reasoning="Camille me gêne."))
    recorder.write(NotebookEntryRecorded(player=WOLF.id, entry=0, note="Camille pivote vite."))
    recorder.write(GameEnded(outcome=Outcome.VILLAGE_WINS))

    assert replay(recorder.journal.events) == plain
