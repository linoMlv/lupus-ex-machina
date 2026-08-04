"""Intent schema.

Intents are a closed, discriminated union: the very same type becomes the
structured output schema of the language models in J7, so it is designed here
rather than translated later.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    RoleAction,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName

adapter: TypeAdapter[Intent] = TypeAdapter(Intent)

THEO = PlayerId("p1")


def test_every_intent_variant_round_trips_through_its_discriminator() -> None:
    intents: tuple[Intent, ...] = (
        TakeTurn(speech="Théo est bien silencieux."),
        TakeTurn(vote=Vote(target=THEO)),
        TakeTurn(speech="Je me décide.", vote=Vote()),
        Wait(),
        RoleAction(action=RoleActionName.DEVOUR, target=THEO),
    )

    for intent in intents:
        assert adapter.validate_python(intent.model_dump()) == intent


# --- The three ways a turn can go (J5.2.1, D-028) ----------------------------


def test_a_turn_can_be_speech_alone() -> None:
    """Said their piece, and left the round open."""
    turn = TakeTurn(speech="Théo est bien silencieux.")

    assert turn.speech is not None
    assert turn.vote is None


def test_a_turn_can_be_speech_and_a_vote_at_once() -> None:
    """The turn a player votes in is the last one they may speak in (D-028)."""
    turn = TakeTurn(speech="J'ai assez entendu.", vote=Vote(target=THEO))

    assert turn.speech is not None
    assert turn.vote is not None


def test_a_turn_can_be_a_vote_alone() -> None:
    """Closing the round without a word."""
    turn = TakeTurn(vote=Vote(target=THEO))

    assert turn.speech is None
    assert turn.vote is not None


def test_a_turn_that_does_neither_is_not_a_turn() -> None:
    """Doing nothing is Wait, and saying so twice would be two ways to wait."""
    with pytest.raises(ValidationError):
        TakeTurn()


def test_a_turn_cannot_speak_without_saying_anything() -> None:
    with pytest.raises(ValidationError):
        TakeTurn(speech="")


# --- Naming, and being named -------------------------------------------------


def test_a_speaker_says_whom_they_are_talking_to_and_whom_they_accuse() -> None:
    """Declared rather than dug out of the words (D-002).

    The bidding pays for being addressed and for being accused, so the engine
    has to know. Parsing it out of French prose would put a parser of French in
    the middle of the rules.
    """
    turn = TakeTurn(speech="Théo, tu mens.", addressed=THEO, accused=THEO)

    assert (turn.addressed, turn.accused) == (THEO, THEO)


def test_naming_nobody_is_the_ordinary_case() -> None:
    turn = TakeTurn(speech="Je ne sais pas encore.")

    assert (turn.addressed, turn.accused) == (None, None)


def test_a_vote_without_a_target_is_a_blank_vote() -> None:
    assert Vote().is_blank
    assert not Vote(target=THEO).is_blank


def test_an_unknown_intent_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "dance"})


def test_an_intent_cannot_be_mutated() -> None:
    intent = TakeTurn(speech="Je vote contre Théo.")

    with pytest.raises(ValidationError):
        intent.speech = "autre chose"


def test_a_role_action_requires_a_target() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": IntentKind.ROLE_ACTION, "action": RoleActionName.DEVOUR})
