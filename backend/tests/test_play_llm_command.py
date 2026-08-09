"""Playing a whole game with real models, from the console (J7, exit criterion 1).

The command is exercised against the fake provider: what is under test is the
wiring — settings read, table seated, game played, report printed — and not the
provider. A test that reached the network would cost money and fail on a train.
"""

import pytest

from lupus_ex_machina.config import Settings
from lupus_ex_machina.llm.answers import BidAnswer, ReflectionAnswer, TurnAnswer
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.personalities import personalities
from lupus_ex_machina.play_llm import configured_provider, main


def answering(schema: type, messages: object) -> str:
    """A plausible answer for each shape, with nothing but a thought in it."""
    if schema is BidAnswer:
        return BidAnswer(urgency=40, intention="Peut-être parler.").model_dump_json()
    if schema is ReflectionAnswer:
        return ReflectionAnswer(reasoning="Ce tour m'a appris peu.").model_dump_json()
    return TurnAnswer(reasoning="J'observe.").model_dump_json()


def test_it_says_what_is_missing_when_no_key_is_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The one thing a user forgets, and it must not read as a crash (D-090)."""
    exit_code = main(["--players", "6"])

    assert exit_code == 1
    assert "LUPUS_LLM_API_KEY" in capsys.readouterr().err


def test_a_whole_game_is_played_and_reported(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert "Victoire" in printed, "the game reached an end"
    assert "Appels aux modèles" in printed, "the budget of a game is reported (GL-7)"


def test_what_a_game_cost_in_calls_and_in_seconds_is_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit criterion 7 of J7: calls *and* latency, measured and written down.

    Both, and read off the provider that knows them (GL-7): a budget of calls
    with no time against it says nothing about whether a game is watchable, and
    a latency nobody prints is a measurement nobody makes.
    """
    main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert "Appels aux modèles" in printed
    assert "secondes" in printed.lower(), "the time those calls took"


def test_the_table_it_deals_is_announced_with_its_temperaments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A spectator sees who plays with what, when the configuration allows it (D-064)."""
    main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert "mistral-small-latest" in printed
    assert any(temperament.name in printed for temperament in personalities().values()), (
        "every seat is announced with the temperament it plays"
    )


def test_a_provider_is_built_from_the_settings_when_a_key_is_there() -> None:
    """Building a client reaches nobody, so this is testable without a network."""
    settings = Settings(llm_api_key="clef-de-test", llm_base_url="https://ailleurs.test/v1")

    assert configured_provider(settings) is not None


def test_no_provider_is_built_without_a_key() -> None:
    assert configured_provider(Settings()) is None
