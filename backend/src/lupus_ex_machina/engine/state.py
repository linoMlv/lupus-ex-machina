"""Game state.

The state is immutable: every transition returns a new state (J2.1.4). Nothing
here is a plain mutable container, so a state cannot be altered through one of
its own fields.

The state holds no winner: the outcome is a pure function of the players still
alive, so storing it would only create a second source of truth.
"""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.phases import Phase, ensure_transition_allowed
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import Team


class Ballot(BaseModel):
    """A vote cast during the day. A missing target is a blank vote (D-027)."""

    model_config = ConfigDict(frozen=True)

    voter: PlayerId
    target: PlayerId | None = None


class NightChoice(BaseModel):
    """A target designated by a player during the night."""

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    target: PlayerId


class GameState(BaseModel):
    """Complete state of a game at a point in time."""

    model_config = ConfigDict(frozen=True)

    players: tuple[Player, ...]
    phase: Phase
    day: int = Field(ge=0)
    ballots: tuple[Ballot, ...] = ()
    night_choices: tuple[NightChoice, ...] = ()

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

    def has_chosen_a_night_target(self, player_id: PlayerId) -> bool:
        """Whether that player already designated a target this night."""
        return any(choice.actor == player_id for choice in self.night_choices)

    # --- Transitions -----------------------------------------------------

    def entering(self, phase: Phase, *, day: int | None = None) -> "GameState":
        """Return the state moved to another phase, checking the move is legal."""
        ensure_transition_allowed(self.phase, phase)
        return self.model_copy(update={"phase": phase, "day": self.day if day is None else day})

    def with_ballot_from(self, voter: PlayerId, target: PlayerId | None = None) -> "GameState":
        """Return the state with one more ballot recorded."""
        ballot = Ballot(voter=voter, target=target)
        return self.model_copy(update={"ballots": (*self.ballots, ballot)})

    def with_night_choice_from(self, actor: PlayerId, target: PlayerId) -> "GameState":
        """Return the state with one more night target recorded."""
        choice = NightChoice(actor=actor, target=target)
        return self.model_copy(update={"night_choices": (*self.night_choices, choice)})

    def with_players_killed(self, victims: Iterable[PlayerId]) -> "GameState":
        """Return the state with the given players dead."""
        doomed = set(victims)
        players = tuple(
            player.killed() if player.id in doomed and player.alive else player
            for player in self.players
        )
        return self.model_copy(update={"players": players})

    def cleared_of_round_choices(self) -> "GameState":
        """Return the state without the ballots and night targets of the round."""
        return self.model_copy(update={"ballots": (), "night_choices": ()})
