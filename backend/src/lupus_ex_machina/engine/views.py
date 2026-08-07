"""Projection of the state onto what a single player may know.

An agent never receives :class:`GameState`; it receives this, and nothing else
reaches its prompt (D-001, GL-3). The rule is subtractive: the projection starts
from what is public and adds only what this player is entitled to — its own
role, and its pack if it has one.

The view also carries the moves that are currently legal. That is not a
convenience for the scripted agents: it is what a language model will be told it
may do (J7), and it keeps the legality in one place, next to the validator —
:mod:`legal_moves`, which derives every one of them from the validator itself.

J3 generalises this into the visibility model, where each fact carries its own
audience (D-009). The boundary drawn here is the one that model formalises.
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine import legal_moves
from lupus_ex_machina.engine.intents import IntentKind, TakeTurn, Vote
from lupus_ex_machina.engine.night import victim_seen_by_the_witch
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName, Team
from lupus_ex_machina.engine.state import GameState


class PublicPlayer(BaseModel):
    """A player as everyone sees them: an identity, a seat, alive or dead.

    Death is always public; only the role of the deceased may stay hidden
    (D-072), and no role appears here at all.
    """

    model_config = ConfigDict(frozen=True)

    id: PlayerId
    name: str
    seat: int
    alive: bool


class SpeechLimits(BaseModel):
    """How many words a player may spend, and on what (D-021).

    Part of the view because the view is the whole of what a model is told
    (GL-3): limits read anywhere else would be the one thing in a prompt the
    projection did not carry. The engine truncates regardless — a limit asked
    for in a prompt is one a model overruns.
    """

    model_config = ConfigDict(frozen=True)

    speech_words: int = Field(ge=1)
    analysis_words: int = Field(ge=1)
    notebook_words: int = Field(ge=1)


class PlayerView(BaseModel):
    """Everything one player knows about the game."""

    model_config = ConfigDict(frozen=True)

    self_id: PlayerId
    role: RoleName
    phase: Phase
    day: int
    players: tuple[PublicPlayer, ...]
    allies: tuple[PlayerId, ...] = ()
    voters: tuple[PlayerId, ...] = ()
    has_voted: bool = False
    allowed_intents: tuple[IntentKind, ...] = ()
    may_speak: bool = False
    """Whether this player still holds the floor (D-013)."""
    may_vote: bool = False
    """Whether this player may still cast a ballot this round (D-024).

    Told apart from :attr:`may_speak` because one turn can do either, both, or
    neither (D-028): the kind of intent alone would not say which halves of it
    the rules would take.
    """
    vote_targets: tuple[PlayerId, ...] = ()
    action_targets: tuple[PlayerId, ...] = ()
    available_actions: tuple[RoleActionName, ...] = ()
    """Powers this player may use right now, empty when they have none."""
    priority_budget: int = 0
    """Points this player may spread over the prey tonight, zero when they may not."""
    limits: SpeechLimits
    """What this player may spend words on, and how many (D-021)."""

    victim_tonight: PlayerId | None = None
    """Whom the pack settled on, shown only to a player who may answer it (D-029).

    The witch is *told* the victim rather than left to guess: her potion of life
    only saves that one player, so without this the view would offer her a power
    and no way to aim it. Everyone else sees nothing here — it is the pack's
    secret until dawn.
    """

    @property
    def living_others(self) -> tuple[PlayerId, ...]:
        """Living players other than oneself."""
        return tuple(
            player.id for player in self.players if player.alive and player.id != self.self_id
        )


def project(state: GameState, viewer: PlayerId) -> PlayerView:
    """Build what ``viewer`` is allowed to know about the current state.

    The legal moves are settled by putting candidates to the validator, so each
    answer is worked out once here and handed down rather than recomputed by
    every field that needs it.
    """
    actions = legal_moves.available_actions(state, viewer)
    designating = legal_moves.may_designate(state, viewer)
    speaking = legal_moves.accepted(state, viewer, TakeTurn(speech="Je vous écoute."))
    voting = legal_moves.accepted(state, viewer, TakeTurn(vote=Vote()))

    return PlayerView(
        self_id=viewer,
        role=state.player(viewer).role,
        phase=state.phase,
        day=state.day,
        players=tuple(
            PublicPlayer(id=player.id, name=player.name, seat=player.seat, alive=player.alive)
            for player in state.players
        ),
        allies=_allies_of(state, viewer),
        voters=tuple(ballot.voter for ballot in state.ballots),
        has_voted=state.has_voted(viewer),
        allowed_intents=legal_moves.allowed_intents(
            state, viewer, actions, designating=designating, taking_a_turn=speaking or voting
        ),
        may_speak=speaking,
        may_vote=voting,
        vote_targets=legal_moves.vote_targets(state, viewer),
        action_targets=legal_moves.action_targets(state, viewer, actions, designating=designating),
        available_actions=actions,
        priority_budget=state.rules.night.priority_budget if designating else 0,
        limits=SpeechLimits(
            speech_words=state.rules.debate.speech_word_limit,
            analysis_words=state.rules.debate.analysis_word_limit,
            notebook_words=state.rules.debate.notebook_word_limit,
        ),
        victim_tonight=_victim_shown_to(state, viewer, actions),
    )


def _victim_shown_to(
    state: GameState, viewer: PlayerId, actions: tuple[RoleActionName, ...]
) -> PlayerId | None:
    """The prey the pack took, shown to whoever holds a power that answers it.

    Tied to the power rather than to the role: the witch sees the victim exactly
    while she still has a potion of life to pour on them, which is the same
    condition the validator puts on the potion itself.
    """
    if RoleActionName.HEAL not in actions:
        return None
    return victim_seen_by_the_witch(state)


def _allies_of(state: GameState, viewer: PlayerId) -> tuple[PlayerId, ...]:
    """Wolves know each other; villagers know no one (D-032)."""
    if state.player(viewer).team is not Team.WEREWOLVES:
        return ()
    return tuple(
        player.id
        for player in state.players
        if player.team is Team.WEREWOLVES and player.id != viewer
    )
