"""The view obeys the same model as the journal (D-009)."""

import pytest

from lupus_ex_machina.engine.events import (
    BallotCast,
    NightResolved,
    PhaseEntered,
    PriorityShared,
    VoteResolved,
)
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import GameResult
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from support.leak_sweeps import (
    played,
    scalars_in,
)

# --- The view handed to an agent obeys the same model ------------------------

#: The facts that move the state along. Replaying the journal up to each of them
#: rebuilds every situation a game actually went through.
STATE_CHANGING = (PhaseEntered, BallotCast, PriorityShared, VoteResolved, NightResolved)

#: Sweeping the views of a whole game means rebuilding it state by state, so
#: this runs on a few games rather than on the corpus.
FEW = range(3)


def moments_of(result: GameResult) -> list[GameState]:
    """Every situation the game went through, rebuilt from its own journal.

    Replaying rather than instrumenting the runner keeps this honest twice over:
    it sweeps the states a journal can actually produce, and it would notice a
    situation the journal fails to describe.
    """
    return [
        replay(result.journal[: rank + 1])
        for rank, event in enumerate(result.journal)
        if isinstance(event.payload, STATE_CHANGING)
    ]


@pytest.mark.parametrize("seed", FEW)
async def test_no_view_ever_carries_a_role_other_than_its_viewers(seed: int) -> None:
    """The projection an agent receives is a view too (D-001, GL-3).

    Held separately from the journal on purpose: the view is what reaches a
    prompt, and nothing but a test ties the two together.
    """
    result = await played(seed)

    for state in moments_of(result):
        for player in state.players:
            readable = set(scalars_in(project(state, player.id).model_dump(mode="json")))
            foreign = {role.value for role in RoleName} - {player.role.value}

            assert not (readable & foreign), f"{player.name} could read {readable & foreign}"


async def test_whom_someone_named_changes_nothing_in_anybody_elses_view() -> None:
    """Two games differing only by a secret must look identical to whoever is not entitled.

    Comparing whole views is what makes this falsifiable: a field that carried
    the target — under any name, at any depth — would make them differ. Even the
    accused must not learn they were named (D-013).

    Swept over several games rather than one: a single seed can go by without a
    named ballot ever being cast, and the property would then be true of nothing
    at all. The count at the end is what refuses that.
    """
    checked = 0
    # The games are played first: awaiting inside the comprehension would make it
    # an asynchronous generator, which is not what the sweep below iterates over.
    games = [await played(seed) for seed in FEW]

    for state in (moment for game in games for moment in moments_of(game)):
        for rank, ballot in enumerate(state.ballots):
            if ballot.target is None:
                continue
            elsewhere = next(
                (
                    other.id
                    for other in state.living
                    if other.id not in (ballot.voter, ballot.target)
                ),
                None,
            )
            if elsewhere is None:
                continue

            altered = state.model_copy(
                update={
                    "ballots": tuple(
                        cast.model_copy(update={"target": elsewhere}) if index == rank else cast
                        for index, cast in enumerate(state.ballots)
                    )
                }
            )
            for viewer in state.players:
                if viewer.id == ballot.voter:
                    continue
                assert project(state, viewer.id) == project(altered, viewer.id)
                checked += 1

    assert checked, "no named ballot was ever compared, so nothing is proven"
