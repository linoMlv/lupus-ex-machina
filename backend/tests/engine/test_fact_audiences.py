"""What each audience means, fact by fact (D-009)."""

from lupus_ex_machina.engine.events import (
    BallotCast,
    NightResolved,
    NotebookEntryRecorded,
    PackRevealed,
    PrioritiesRevealed,
    PriorityShared,
    PrivateReasoningRecorded,
    RunoffOpened,
    VoteResolved,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient, Visibility
from support.facts import A_FEW_POINTS, A_SPREAD, VILLAGER, WOLF

# --- What the audiences mean -------------------------------------------------


def test_a_named_ballot_reaches_its_author_and_nobody_else() -> None:
    """A voter may re-read their own vote; the table may not (D-013)."""
    ballot = BallotCast(voter=WOLF, target=VILLAGER)

    assert ballot.audience.reaches(Recipient(player=WOLF, role=RoleName.WEREWOLF))
    assert not ballot.audience.reaches(Recipient(player=VILLAGER, role=RoleName.VILLAGER))
    assert ballot.audience.reaches(SPECTATOR)


def test_a_blank_ballot_is_public_the_moment_it_is_cast() -> None:
    """Skipping costs the floor *and* reveals the choice (D-027)."""
    assert BallotCast(voter=WOLF, target=None).audience == Visibility.public()


def test_death_is_public_whatever_took_the_player() -> None:
    """Never configurable — only the role of the deceased may stay hidden (D-072)."""
    assert VoteResolved(eliminated=VILLAGER).audience == Visibility.public()
    assert NightResolved(victims=(VILLAGER,)).audience == Visibility.public()


def test_the_pack_channel_never_leaves_the_pack() -> None:
    villager = Recipient(player=VILLAGER, role=RoleName.VILLAGER)

    for spoken in (
        PriorityShared(actor=WOLF, allocations=(A_FEW_POINTS,)),
        PrioritiesRevealed(shares=(A_SPREAD,)),
        RunoffOpened(targets=(VILLAGER,)),
        PackRevealed(members=(WOLF,)),
    ):
        assert not spoken.audience.reaches(villager)


def test_a_spread_is_its_own_wolf_s_until_the_designation_is_settled() -> None:
    """The pack designates blind (D-085): a wolf reads nobody's points but his own.

    What each of them weighed is laid out afterwards, by a fact of its own —
    which is what lets the spreads be blind without being secret for good.
    """
    other_wolf = Recipient(player=PlayerId("p9"), role=RoleName.WEREWOLF)
    spread = PriorityShared(actor=WOLF, allocations=(A_FEW_POINTS,))

    assert not spread.audience.reaches(other_wolf)
    assert PrioritiesRevealed(shares=(A_SPREAD,)).audience.reaches(other_wolf)


def test_inner_thoughts_belong_to_their_author_and_the_spectator() -> None:
    """The separation of thought and speech is held by the code (D-004, GL-3)."""
    for payload in (
        PrivateReasoningRecorded(player=WOLF, reasoning="Je vais accuser Camille."),
        NotebookEntryRecorded(player=WOLF, entry=0, note="Camille pivote vite."),
    ):
        assert payload.audience == Visibility.for_player(WOLF)
