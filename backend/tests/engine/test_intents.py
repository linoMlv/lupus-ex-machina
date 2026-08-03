"""Intent schema.

Intents are a closed, discriminated union: the very same type becomes the
structured output schema of the language models in J7, so it is designed here
rather than translated later.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    IntentKind,
    RoleAction,
    RoleActionName,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId

adapter: TypeAdapter[Intent] = TypeAdapter(Intent)


def test_every_intent_variant_round_trips_through_its_discriminator() -> None:
    intents: tuple[Intent, ...] = (
        Speak(speech="Théo est bien silencieux."),
        CastVote(target=PlayerId("p1")),
        CastVote(),
        Wait(),
        RoleAction(action=RoleActionName.DEVOUR, target=PlayerId("p1")),
    )

    for intent in intents:
        assert adapter.validate_python(intent.model_dump()) == intent


def test_a_vote_without_a_target_is_a_blank_vote() -> None:
    assert CastVote().is_blank
    assert not CastVote(target=PlayerId("p1")).is_blank


def test_an_unknown_intent_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "dance"})


def test_an_intent_cannot_be_mutated() -> None:
    intent = Speak(speech="Je vote contre Théo.")

    with pytest.raises(ValidationError):
        intent.speech = "autre chose"


def test_a_role_action_requires_a_target() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": IntentKind.ROLE_ACTION, "action": RoleActionName.DEVOUR})
