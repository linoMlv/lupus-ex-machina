"""What every fact of the game is, and the list of the kinds there are.

Every fact declares the audience it is addressed to, and it declares it *itself*
rather than at the place it is recorded: a caller cannot forget, and cannot get
it wrong twice in two different ways. :class:`Fact` is abstract on that single
property, so a type that says nothing about who may know it cannot even be
built (D-009).
"""

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.visibility import Visibility


class EventKind(StrEnum):
    """Discriminator of the fact union."""

    PLAYER_SEATED = "player_seated"
    ROLE_ASSIGNED = "role_assigned"
    PACK_REVEALED = "pack_revealed"
    PHASE_ENTERED = "phase_entered"
    SPEECH_DELIVERED = "speech_delivered"
    BALLOT_CAST = "ballot_cast"
    BALLOT_ANNOUNCED = "ballot_announced"
    NIGHT_POWER_USED = "night_power_used"
    POWER_SPENT = "power_spent"
    SHOT_FIRED = "shot_fired"
    SEER_INSPECTED = "seer_inspected"
    SEER_FINDING_ANNOUNCED = "seer_finding_announced"
    PRIORITY_SHARED = "priority_shared"
    RUNOFF_OPENED = "runoff_opened"
    PACK_RUNOFF_OPENED = "pack_runoff_opened"
    VOTE_RESOLVED = "vote_resolved"
    NIGHT_RESOLVED = "night_resolved"
    ROLE_REVEALED = "role_revealed"
    INTENT_REJECTED = "intent_rejected"
    GAME_ENDED = "game_ended"
    PRIVATE_REASONING_RECORDED = "private_reasoning_recorded"
    NOTEBOOK_ENTRY_RECORDED = "notebook_entry_recorded"
    NOTEBOOK_ENTRY_DROPPED = "notebook_entry_dropped"
    FLOOR_AUCTIONED = "floor_auctioned"
    VOTE_FORCED = "vote_forced"
    BALLOTS_REVEALED = "ballots_revealed"
    PRIORITIES_REVEALED = "priorities_revealed"
    FLOOR_CLAIMED = "floor_claimed"


class Fact(BaseModel, ABC):
    """Something that happened, and the audience entitled to know it.

    Declaring an audience is what makes a fact recordable: the property is
    abstract so the guarantee is structural rather than a convention to
    remember.
    """

    model_config = ConfigDict(frozen=True)

    @property
    @abstractmethod
    def audience(self) -> Visibility:
        """Who may know this."""
