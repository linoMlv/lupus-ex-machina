"""Every fact declares who may know it, and cannot be built without (D-009)."""

import pytest

from lupus_ex_machina.engine.events import (
    EventPayload,
    Fact,
)
from lupus_ex_machina.engine.visibility import Visibility
from support.facts import AUDIENCES, payload_types

# --- Every fact declares who may know it (D-009) -----------------------------


@pytest.mark.parametrize(("payload", "expected"), AUDIENCES, ids=lambda value: str(value)[:60])
def test_every_fact_is_addressed_to_the_declared_audience(
    payload: EventPayload, expected: Visibility
) -> None:
    assert payload.audience == expected


def test_the_table_covers_every_kind_of_fact() -> None:
    """Adding a fact without deciding who may know it must fail here.

    Without this, a new event type would default to whatever its author wrote
    and no test would ever disagree.
    """
    assert {type(payload) for payload, _ in AUDIENCES} == payload_types()


def test_a_fact_that_declares_no_audience_cannot_be_built() -> None:
    """The guarantee is structural, not a convention to remember."""

    class Unlabelled(Fact):
        """A fact whose author forgot to say who may know it."""

    with pytest.raises(TypeError, match="audience"):
        Unlabelled()  # type: ignore[abstract]
