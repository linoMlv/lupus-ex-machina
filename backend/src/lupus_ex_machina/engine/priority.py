"""Adding up what the pack wants (D-008).

Each wolf spreads a fixed budget over the prey it would rather take, negative
points included, and the designation is the tally. The budget is the whole point:
with a free score, a wolf putting the maximum on everyone drowns out the others,
and the system would reward vehemence rather than conviction.

A total has to be strictly positive to designate. Points that cancel out, or
nothing but aversion, describe a pack that did not pick a prey — not a pack whose
least-hated member dies. Nights without a victim are a normal outcome of the
rules (D-078), so there is nothing to force here.

Pure on purpose: who is asked, and whether they are asked a second time after a
tie, belongs to the night. What a set of answers adds up to belongs here.
"""

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import PriorityShare


class TargetTotal(BaseModel):
    """What one prey ended up worth to the pack."""

    model_config = ConfigDict(frozen=True)

    target: PlayerId
    total: int


class Tally(BaseModel):
    """What a night's shares add up to, most wanted first."""

    model_config = ConfigDict(frozen=True)

    totals: tuple[TargetTotal, ...]

    def total_for(self, target: PlayerId) -> int:
        """Points that prey ended up with. Zero when nobody named them."""
        return next((entry.total for entry in self.totals if entry.target == target), 0)

    @property
    def leaders(self) -> tuple[PlayerId, ...]:
        """The prey the pack wants most, empty when it wants nobody."""
        wanted = [entry for entry in self.totals if entry.total > 0]
        if not wanted:
            return ()

        best = wanted[0].total
        return tuple(entry.target for entry in wanted if entry.total == best)

    @property
    def designated(self) -> PlayerId | None:
        """The prey the pack took, or ``None`` when it did not settle on one.

        A tie spares everyone, exactly as at the day vote (D-050). The silent
        runoff that may precede that outcome is run by the night.
        """
        leaders = self.leaders
        return leaders[0] if len(leaders) == 1 else None


def tally(shares: Iterable[PriorityShare]) -> Tally:
    """Add up every wolf's spread into one ordering of the prey."""
    points: Counter[PlayerId] = Counter()
    for share in shares:
        for allocation in share.allocations:
            points[allocation.target] += allocation.points

    return Tally(
        totals=tuple(
            TargetTotal(target=target, total=total)
            for target, total in sorted(points.items(), key=lambda entry: -entry[1])
        )
    )
