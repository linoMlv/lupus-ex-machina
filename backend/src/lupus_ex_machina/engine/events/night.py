"""The night: powers used in the dark, what the pack weighed, and what it cost.

Almost everything here is addressed to one player. A night is silent (D-083) and
settled in one go at the end (D-006), so what is recorded while it runs is what
each player did on their own — never what it came to.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.night import Revelation
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.visibility import Visibility


class RevealedShare(BaseModel):
    """One wolf's spread, as the pack is shown it afterwards."""

    model_config = ConfigDict(frozen=True)

    wolf: PlayerId
    allocations: tuple[PriorityPoint, ...]


class NightPowerUsed(Fact):
    """A player used a single-target power on someone during the night.

    What they did, not what it came to: the effect is settled with the rest of
    the night (D-006), and what a seer learns is a fact of its own.
    """

    kind: Literal[EventKind.NIGHT_POWER_USED] = EventKind.NIGHT_POWER_USED
    actor: PlayerId
    action: RoleActionName
    target: PlayerId

    @property
    def audience(self) -> Visibility:
        """Its author: a power used in the dark is nobody else's business."""
        return Visibility.for_player(self.actor)


class PowerSpent(Fact):
    """A power that works once has now been used up (D-029).

    Recorded on its own because it outlives the round: the choice that spent it
    is wiped when the night closes, and a game rebuilt from the journal would
    otherwise hand the potion back.
    """

    kind: Literal[EventKind.POWER_SPENT] = EventKind.POWER_SPENT
    actor: PlayerId
    action: RoleActionName

    @property
    def audience(self) -> Visibility:
        """Its holder: the table never learns what is left in the cupboard."""
        return Visibility.for_player(self.actor)


class SeerInspected(Fact):
    """What the seer read on the player she looked at (D-031)."""

    kind: Literal[EventKind.SEER_INSPECTED] = EventKind.SEER_INSPECTED
    seer: PlayerId
    target: PlayerId
    revelation: Revelation

    @property
    def audience(self) -> Visibility:
        """Hers alone, and the spectator's."""
        return Visibility.for_player(self.seer)


class SeerFindingAnnounced(Fact):
    """The table is told what the seer found, never on whom (D-031).

    A fact of its own rather than the private one with a wider audience: the
    name of the player she looked at must not travel with it, and the only way
    to be sure of that is for it not to be there.
    """

    kind: Literal[EventKind.SEER_FINDING_ANNOUNCED] = EventKind.SEER_FINDING_ANNOUNCED
    revelation: Revelation

    @property
    def audience(self) -> Visibility:
        """Public, which is the whole point of the option."""
        return Visibility.public()


class PriorityShared(Fact):
    """A wolf spreads its points over the prey (D-008).

    Its author's own, not the pack's (D-085). The wolves designate blind, so a
    spread another wolf could read while there is still time to answer it would
    turn the night into the herd vote the weighting exists to prevent.
    """

    kind: Literal[EventKind.PRIORITY_SHARED] = EventKind.PRIORITY_SHARED
    actor: PlayerId
    allocations: tuple[PriorityPoint, ...]

    @property
    def audience(self) -> Visibility:
        """The wolf who spread them, and nobody else until the designation."""
        return Visibility.for_player(self.actor)


class PrioritiesRevealed(Fact):
    """What each wolf weighed, laid out for the pack (D-085).

    The night's counterpart to the count of the day (D-082), and the reason the
    spreads can be blind without the pack being blindfolded for good: what makes
    a spread blind is that nobody can *answer* it, not that it stays secret.

    Produced only when the configuration says so — an option decides whether a
    fact exists, never who may read one (D-009).
    """

    kind: Literal[EventKind.PRIORITIES_REVEALED] = EventKind.PRIORITIES_REVEALED
    shares: tuple[RevealedShare, ...] = ()

    @property
    def audience(self) -> Visibility:
        """The pack, once it has designated its prey."""
        return Visibility.for_role(RoleName.WEREWOLF)


class RunoffOpened(Fact):
    """The pack tied, so a silent second round is held between the ex aequo (D-062)."""

    kind: Literal[EventKind.RUNOFF_OPENED] = EventKind.RUNOFF_OPENED
    targets: tuple[PlayerId, ...]

    @property
    def audience(self) -> Visibility:
        """The pack: the tie happened on its own channel."""
        return Visibility.for_role(RoleName.WEREWOLF)


class NightResolved(Fact):
    """The night is over. It may take nobody, or more than one (D-029)."""

    kind: Literal[EventKind.NIGHT_RESOLVED] = EventKind.NIGHT_RESOLVED
    victims: tuple[PlayerId, ...] = ()

    @property
    def audience(self) -> Visibility:
        """Public: death is never hidden (D-072)."""
        return Visibility.public()
