"""The fragments a prompt is assembled from, one per thing a seat is told.

Each of these turns one part of a view into the French a model reads. They
are kept apart from the three prompts themselves so that adding something a
seat should know is a matter of writing a fragment and naming it in a
template, never of editing the assembly.
"""

import tomllib
from collections.abc import Sequence
from functools import cache
from importlib import resources
from string import Template
from typing import Any

from lupus_ex_machina.engine.events import Event, SpeechDelivered
from lupus_ex_machina.engine.notebook import notebook_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import ROLES, RoleName
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.labels import ACTION_LABELS, PHASE_LABELS, ROLE_LABELS
from lupus_ex_machina.llm.tagging import speech_block

#: Where the prose lives. Read once per prompt rather than cached: a game is
#: hundreds of calls over minutes, and a file read is not what costs.
PROMPTS = resources.files(__package__) / "prompts"


@cache
def _pieces() -> dict[str, Any]:
    """The sentences a prompt is assembled from, read once."""
    parsed: dict[str, Any] = tomllib.loads((PROMPTS / "pieces.toml").read_text(encoding="utf-8"))
    return parsed


def piece(path: str) -> Template:
    """One sentence of the catalogue, addressed as ``section.name``."""
    section, name = path.split(".")
    text: str = _pieces()[section][name]
    return Template(text.strip())


def template(name: str) -> Template:
    """The prompt of that name, as a template ready to be filled."""
    return Template((PROMPTS / f"{name}.txt").read_text(encoding="utf-8"))


def _role_brief(role: RoleName) -> str:
    """What this role is, and what it may do, in one paragraph."""
    powers = ROLES[role].actions
    if not powers:
        return piece("role.without_power").substitute(role=ROLE_LABELS[role])
    return piece("role.with_powers").substitute(
        role=ROLE_LABELS[role],
        powers=", ".join(sorted(ACTION_LABELS[power] for power in powers)),
    )


def _what_they_know(view: PlayerView) -> str:
    """The one thing a role may know about the others: its own pack (D-032)."""
    if not view.allies:
        return piece("knowledge.alone").template
    return piece("knowledge.pack").substitute(
        allies=", ".join(sorted(_name_of(view, ally) for ally in view.allies))
    )


def _moment(view: PlayerView) -> str:
    """Where the game stands, in a sentence."""
    return piece("moment.now").substitute(phase=PHASE_LABELS[view.phase], day=view.day)


def _table(view: PlayerView) -> str:
    """Who is at the table, alive or dead. Death is public, roles are not (D-072)."""
    return "\n".join(
        f"- {player.name}{'' if player.alive else ' (mort)'}"
        + (" — toi" if player.id == view.self_id else "")
        for player in view.players
    )


def _notebook(view: PlayerView, journal: Sequence[Event]) -> str:
    """The player's own notes, numbered as they will refer to them (D-005)."""
    written = notebook_of(journal, view.self_id)
    if not written:
        return piece("transcript.nothing_yet").template
    return "\n".join(f"[{note.entry}] {note.note}" for note in written)


def _speeches(journal: Sequence[Event]) -> list[tuple[int, SpeechDelivered]]:
    """Every speech of a journal, with the day it was said on."""
    return [
        (event.day, event.payload)
        for event in journal
        if isinstance(event.payload, SpeechDelivered)
    ]


def _transcript(view: PlayerView, journal: Sequence[Event]) -> str:
    """Everything said in front of this player, each speech inside its block (D-067)."""
    blocks = [
        speech_block(
            speaker=_name_of(view, spoken.speaker),
            day=day,
            order=order,
            speech=spoken.speech,
        )
        for order, (day, spoken) in enumerate(_speeches(journal), start=1)
    ]
    return "\n".join(blocks) if blocks else piece("transcript.nothing_yet").template


def _last_word(view: PlayerView, journal: Sequence[Event]) -> str:
    """The turn at the floor this auction answers, which is all a bid needs."""
    said = _speeches(journal)
    if not said:
        return piece("transcript.nobody_spoke").template

    day, last = said[-1]
    return piece("transcript.last_word").substitute(
        block=speech_block(
            speaker=_name_of(view, last.speaker), day=day, order=len(said), speech=last.speech
        )
    )


def _moves(view: PlayerView) -> str:
    """What the rules would take from this player right now, in French.

    Read off the view rather than restated from the rules: the view is derived
    from the validator, so what is offered here is exactly what will be accepted.
    """
    offered = [
        _speaking(view),
        _voting(view),
        _designating(view),
        _using_a_power(view),
    ]
    listed = [line for line in offered if line is not None]
    if not listed:
        return piece("moves.nothing").template
    return "\n".join(f"- {line}" for line in listed)


def _speaking(view: PlayerView) -> str | None:
    if not view.may_speak:
        return None
    return piece("moves.speaking").template


def _voting(view: PlayerView) -> str | None:
    if not view.may_vote:
        return None
    if not view.vote_targets:
        return piece("moves.blank_vote_only").template
    return piece("moves.voting").substitute(
        targets=", ".join(sorted(_name_of(view, target) for target in view.vote_targets))
    )


def _designating(view: PlayerView) -> str | None:
    if not view.priority_budget:
        return None
    return piece("moves.designating").substitute(
        budget=view.priority_budget,
        targets=", ".join(sorted(_name_of(view, target) for target in view.action_targets)),
    )


def _using_a_power(view: PlayerView) -> str | None:
    if not view.available_actions:
        return None
    shown = (
        piece("moves.victim").substitute(victim=_name_of(view, view.victim_tonight))
        if view.victim_tonight is not None
        else ""
    )
    return piece("moves.power").substitute(
        powers=", ".join(sorted(ACTION_LABELS[action] for action in view.available_actions)),
        targets=", ".join(sorted(_name_of(view, target) for target in view.action_targets)),
        victim=shown,
    )


def _name_of(view: PlayerView, player: PlayerId) -> str:
    """The public name of a player, as everyone at the table says it.

    Names, never identifiers: what goes to a model is what is said out loud.
    """
    return next(other.name for other in view.players if other.id == player)
