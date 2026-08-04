"""Game state.

The state is immutable: every transition returns a new state (J2.1.4). Nothing
here is a plain mutable container, so a state cannot be altered through one of
its own fields.

The state holds no winner: the outcome is a pure function of the players still
alive, so storing it would only create a second source of truth.
"""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.phases import Phase, ensure_transition_allowed
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, Team


class Ballot(BaseModel):
    """A vote cast during the day. A missing target is a blank vote (D-027)."""

    model_config = ConfigDict(frozen=True)

    voter: PlayerId
    target: PlayerId | None = None


class NightChoice(BaseModel):
    """A power a player used on someone during the night.

    The action travels with the target because the night holds several of them
    at once (D-006): they are collected as they are played and settled together
    at the end, so each one has to say what it was.
    """

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    action: RoleActionName
    target: PlayerId


class SpentPower(BaseModel):
    """A one-shot power its holder has now used up.

    Kept apart from the choices of a round, which are wiped as each round ends:
    a potion is spent for the rest of the game, not for the night (D-029).
    """

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    action: RoleActionName


class PriorityShare(BaseModel):
    """One wolf's spread of the night's budget over the prey (D-008)."""

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    allocations: tuple[PriorityPoint, ...]


class GameState(BaseModel):
    """Complete state of a game at a point in time."""

    model_config = ConfigDict(frozen=True)

    players: tuple[Player, ...]
    phase: Phase
    day: int = Field(ge=0)
    ballots: tuple[Ballot, ...] = ()
    night_choices: tuple[NightChoice, ...] = ()
    priority_shares: tuple[PriorityShare, ...] = ()
    spent_powers: tuple[SpentPower, ...] = ()
    runoff_targets: tuple[PlayerId, ...] = ()
    """Whom a silent second round is restricted to, empty outside one (D-062).

    Carried by the state rather than by whoever runs the vote, because the view
    handed to an agent is derived from the state alone: a restriction only the
    caller knew about would offer moves the validator refuses.
    """

    @classmethod
    def initial(cls, players: Iterable[Player]) -> "GameState":
        """Build the state a game starts from: Night 0, before any action."""
        return cls(players=tuple(players), phase=Phase.NIGHT_ZERO, day=0)

    # --- Queries ---------------------------------------------------------

    @property
    def living(self) -> tuple[Player, ...]:
        """Players still alive."""
        return tuple(player for player in self.players if player.alive)

    def living_of_team(self, team: Team) -> tuple[Player, ...]:
        """Living players of a given team."""
        return tuple(player for player in self.living if player.team is team)

    def player(self, player_id: PlayerId) -> Player:
        """Return a player by identity, dead or alive."""
        for player in self.players:
            if player.id == player_id:
                return player
        raise KeyError(f"Unknown player {player_id}")

    def has_player(self, player_id: PlayerId) -> bool:
        """Whether that identity belongs to the game."""
        return any(player.id == player_id for player in self.players)

    def is_alive(self, player_id: PlayerId) -> bool:
        """Whether that player is alive. An unknown player is not."""
        return any(player.id == player_id and player.alive for player in self.players)

    def has_voted(self, player_id: PlayerId) -> bool:
        """Whether that player already cast a ballot this round (D-013, D-024)."""
        return any(ballot.voter == player_id for ballot in self.ballots)

    def has_acted_tonight(self, player_id: PlayerId) -> bool:
        """Whether that player already used their power this night.

        One move per night, whichever shape it took: a single target, or the
        pack's weighted spread. The witch's "one potion per turn" (D-029) falls
        out of this rather than being restated.
        """
        return any(choice.actor == player_id for choice in self.night_choices) or any(
            share.actor == player_id for share in self.priority_shares
        )

    # --- Transitions -----------------------------------------------------

    def entering(self, phase: Phase, *, day: int | None = None) -> "GameState":
        """Return the state moved to another phase, checking the move is legal."""
        ensure_transition_allowed(self.phase, phase)
        return self.model_copy(update={"phase": phase, "day": self.day if day is None else day})

    def with_ballot_from(self, voter: PlayerId, target: PlayerId | None = None) -> "GameState":
        """Return the state with one more ballot recorded."""
        ballot = Ballot(voter=voter, target=target)
        return self.model_copy(update={"ballots": (*self.ballots, ballot)})

    def has_spent(self, player_id: PlayerId, action: RoleActionName) -> bool:
        """Whether that player has already used up that one-shot power."""
        return any(
            spent.actor == player_id and spent.action is action for spent in self.spent_powers
        )

    def with_night_choice_from(
        self, actor: PlayerId, action: RoleActionName, target: PlayerId
    ) -> "GameState":
        """Return the state with one more single-target night power recorded."""
        choice = NightChoice(actor=actor, action=action, target=target)
        return self.model_copy(update={"night_choices": (*self.night_choices, choice)})

    def with_priority_share_from(
        self, actor: PlayerId, allocations: tuple[PriorityPoint, ...]
    ) -> "GameState":
        """Return the state with one more wolf's spread recorded."""
        share = PriorityShare(actor=actor, allocations=allocations)
        return self.model_copy(update={"priority_shares": (*self.priority_shares, share)})

    def reopened_for_runoff(self, targets: Iterable[PlayerId]) -> "GameState":
        """Return the state with a silent second round open between those players.

        What the first round collected is dropped: the runoff is a fresh vote,
        not an amendment of the one that tied (D-050).
        """
        return self.model_copy(
            update={
                "ballots": (),
                "priority_shares": (),
                "runoff_targets": tuple(targets),
            }
        )

    def with_power_spent_by(self, actor: PlayerId, action: RoleActionName) -> "GameState":
        """Return the state with that one-shot power used up for good."""
        spent = SpentPower(actor=actor, action=action)
        return self.model_copy(update={"spent_powers": (*self.spent_powers, spent)})

    def with_players_killed(self, victims: Iterable[PlayerId]) -> "GameState":
        """Return the state with the given players dead."""
        doomed = set(victims)
        players = tuple(
            player.killed() if player.id in doomed and player.alive else player
            for player in self.players
        )
        return self.model_copy(update={"players": players})

    def cleared_of_round_choices(self) -> "GameState":
        """Return the state without anything the round collected."""
        return self.model_copy(
            update={
                "ballots": (),
                "night_choices": (),
                "priority_shares": (),
                "runoff_targets": (),
            }
        )
