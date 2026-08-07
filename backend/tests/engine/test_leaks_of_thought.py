"""Thought never crosses into speech (J3.2.3, D-004, GL-3)."""

import pytest

from lupus_ex_machina.engine.events import (
    NotebookEntryRecorded,
    PrivateReasoningRecorded,
)
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient
from support.leak_sweeps import leaves_of

# --- J3.2.3 — thought never crosses into speech (D-004) ----------------------

TABLE = (
    Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER),
)

SECRET_THOUGHT = "Basile est mon complice, il ne faut surtout pas le trahir."
SECRET_NOTE = "Camille se méfie de moi depuis hier."


def a_journal_of_inner_thoughts() -> Journal:
    """A journal where every player thinks and writes, which J7 will produce."""
    journal = Journal()
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    for player in TABLE:
        journal.record(
            PrivateReasoningRecorded(player=player.id, reasoning=SECRET_THOUGHT), at=state
        )
        journal.record(NotebookEntryRecorded(player=player.id, entry=0, note=SECRET_NOTE), at=state)
    return journal


@pytest.mark.parametrize("player", TABLE, ids=lambda player: player.name)
def test_a_player_reads_their_own_thoughts_and_nobody_elses(player: Player) -> None:
    seen = project_journal(a_journal_of_inner_thoughts().events, Recipient.of(player))
    authors = {
        event.payload.player  # type: ignore[union-attr]
        for event in seen
    }

    assert authors == {player.id}, "thought and notebook belong to their author alone"
    assert len(seen) == 2, "both of them, and only theirs"


def test_the_spectator_reads_every_inner_thought() -> None:
    """Omniscience is the point of the spectator mode (D-004)."""
    journal = a_journal_of_inner_thoughts()

    assert len(project_journal(journal.events, SPECTATOR)) == len(journal)


@pytest.mark.parametrize("player", TABLE, ids=lambda player: player.name)
def test_no_word_of_another_players_thoughts_can_be_read(player: Player) -> None:
    """Searched for as a value, so a leak under any other field name still fails."""
    others = [other for other in TABLE if other.id != player.id]
    journal = Journal()
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)
    for other in others:
        journal.record(
            PrivateReasoningRecorded(player=other.id, reasoning=SECRET_THOUGHT), at=state
        )
        journal.record(NotebookEntryRecorded(player=other.id, entry=0, note=SECRET_NOTE), at=state)

    readable = leaves_of(project_journal(journal.events, Recipient.of(player)))

    assert SECRET_THOUGHT not in readable
    assert SECRET_NOTE not in readable
