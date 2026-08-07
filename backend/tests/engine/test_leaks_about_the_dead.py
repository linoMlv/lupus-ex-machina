"""Death is public, the role of the dead is configurable (J3.2.2, D-080)."""

import pytest

from lupus_ex_machina.engine.events import (
    NightResolved,
    RoleRevealed,
    VoteResolved,
)
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.rules import GameRules, InformationOptions
from support.leak_sweeps import (
    CORPUS,
    SAMPLE,
    everyone_at,
    payloads_of,
    played,
)

# --- J3.2.2 — death is public, the role of the dead is configurable ----------


@pytest.mark.parametrize("seed", CORPUS)
async def test_every_death_reaches_every_single_recipient(seed: int) -> None:
    """Death is never configurable, whatever took the player (D-072)."""
    result = await played(seed)
    deaths = {
        event.sequence
        for event in payloads_of(result.journal, VoteResolved)
        + payloads_of(result.journal, NightResolved)
    }
    assert deaths, "a game where nobody ever died would prove nothing here"

    for recipient in everyone_at(result.state):
        seen = {event.sequence for event in project_journal(result.journal, recipient)}

        assert deaths <= seen


@pytest.mark.parametrize("seed", SAMPLE)
async def test_the_role_of_the_dead_reaches_everyone_when_it_is_revealed(seed: int) -> None:
    result = await played(
        seed, rules=GameRules(information=InformationOptions(reveal_role_on_death=True))
    )
    revelations = {event.sequence for event in payloads_of(result.journal, RoleRevealed)}
    assert revelations, "nothing was revealed, so nothing is proven"

    for recipient in everyone_at(result.state):
        seen = {event.sequence for event in project_journal(result.journal, recipient)}

        assert revelations <= seen


@pytest.mark.parametrize("seed", SAMPLE)
async def test_a_hidden_role_stays_hidden_even_once_its_holder_is_dead(seed: int) -> None:
    """The option decides whether the fact happens, never who may read it."""
    result = await played(
        seed, rules=GameRules(information=InformationOptions(reveal_role_on_death=False))
    )

    assert not payloads_of(result.journal, RoleRevealed)
    assert any(not player.alive for player in result.state.players), "somebody did die"
