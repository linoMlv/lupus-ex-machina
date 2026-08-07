"""No fact of a higher visibility reaches a projection (J3.2.1, D-009)."""

import pytest

from lupus_ex_machina.engine.events import (
    BallotCast,
    IntentRejected,
    PackRevealed,
    PriorityShared,
)
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.roles import RoleName, Team
from lupus_ex_machina.engine.rules import GameRules, InformationOptions, RoleOptions
from lupus_ex_machina.engine.visibility import Recipient
from support.leak_sweeps import (
    CORPUS,
    SAMPLE,
    everyone_at,
    leaves_of,
    payloads_of,
    played,
    played_with_a_rogue,
)

# --- J3.2.1 — no fact of a higher visibility reaches a projection ------------


@pytest.mark.parametrize("seed", CORPUS)
async def test_a_projection_only_ever_holds_facts_its_recipient_is_entitled_to(seed: int) -> None:
    result = await played(seed)

    for recipient in everyone_at(result.state):
        for event in project_journal(result.journal, recipient):
            assert event.is_visible_to(recipient), f"{event.payload.kind} reached {recipient}"


async def test_the_corpus_actually_hides_things_from_everyone() -> None:
    """Guard the guard: over a game where nothing is secret, every test above passes."""
    result = await played(seed=1)

    for recipient in everyone_at(result.state):
        withheld = len(result.journal) - len(project_journal(result.journal, recipient))
        if recipient.is_spectator:
            assert withheld == 0, "the spectator is omniscient"
        else:
            assert withheld > 0, f"nothing was ever hidden from {recipient}"


@pytest.mark.parametrize("seed", SAMPLE)
async def test_no_player_can_read_a_role_other_than_their_own(seed: int) -> None:
    """The one secret the whole game turns on, searched for under any field.

    Run with every setting that hands a role out switched off — no revelation at
    death, and a seer who only reads "wolf or not". Any role name a player can
    read is then necessarily a leak, which is what makes the sweep worth running.
    What the seer is *entitled* to read is a rule of her own, tested with her.
    """
    result = await played(
        seed,
        rules=GameRules(
            information=InformationOptions(reveal_role_on_death=False),
            roles=RoleOptions(seer_learns_exact_role=False),
        ),
    )

    for player in result.state.players:
        readable = leaves_of(project_journal(result.journal, Recipient.of(player)))
        foreign = {role.value for role in RoleName} - {player.role.value}

        assert not (readable & foreign), f"{player.name} could read {readable & foreign}"


@pytest.mark.parametrize("seed", SAMPLE)
async def test_nobody_learns_whom_another_player_voted_for(seed: int) -> None:
    """Who voted is the pressure of the round; for whom is not (D-013)."""
    result = await played(seed)

    for player in result.state.players:
        readable = payloads_of(project_journal(result.journal, Recipient.of(player)), BallotCast)

        for event in readable:
            ballot = event.payload
            assert isinstance(ballot, BallotCast)
            assert ballot.voter == player.id or ballot.target is None, (
                "only one's own ballots, and the blank ones everybody sees (D-027)"
            )


@pytest.mark.parametrize("seed", SAMPLE)
async def test_a_voter_can_always_re_read_their_own_ballot(seed: int) -> None:
    """The counterpart of the rule above, and what an agent needs in J7.

    A player keeps analysing after voting (D-028), so their own vote has to stay
    part of what they know.
    """
    result = await played(seed)

    for player in result.state.players:
        own = {
            event.sequence
            for event in payloads_of(result.journal, BallotCast)
            if isinstance(event.payload, BallotCast) and event.payload.voter == player.id
        }
        readable = {
            event.sequence
            for event in payloads_of(
                project_journal(result.journal, Recipient.of(player)), BallotCast
            )
        }

        assert own, f"{player.name} never voted, so nothing is proven"
        assert own <= readable


@pytest.mark.parametrize("seed", SAMPLE)
async def test_the_channel_of_the_pack_never_reaches_a_villager(seed: int) -> None:
    """The reason a visibility model exists at all (D-007)."""
    result = await played(seed)

    for player in result.state.players:
        seen = project_journal(result.journal, Recipient.of(player))
        pack_facts = payloads_of(seen, PackRevealed) + payloads_of(seen, PriorityShared)

        if player.team is Team.WEREWOLVES:
            assert pack_facts, "a wolf belongs to the channel"
        else:
            assert not pack_facts, f"{player.name} could read the pack channel"


@pytest.mark.parametrize("seed", SAMPLE)
async def test_nobody_at_the_table_learns_that_an_intent_was_refused(seed: int) -> None:
    """Fumbling stays between the engine and the audience."""
    result = await played_with_a_rogue(seed)

    assert payloads_of(result.journal, IntentRejected), "no refusal happened, so nothing is proven"

    for player in result.state.players:
        seen = project_journal(result.journal, Recipient.of(player))

        assert not payloads_of(seen, IntentRejected)
