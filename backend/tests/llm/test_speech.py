"""Cutting what a model produced down to what the rules allow (D-021, D-023)."""

from lupus_ex_machina.llm.speech import sentences, truncated


def test_a_speech_within_its_budget_comes_back_untouched() -> None:
    assert truncated("Je me méfie de Théo.", 50) == "Je me méfie de Théo."


def test_a_speech_over_its_budget_is_cut_and_says_so() -> None:
    """Applied by the engine, not asked for in the prompt: a model overruns (D-021)."""
    assert truncated("un deux trois quatre cinq", 3) == "un deux trois…"


def test_the_cut_falls_between_words_rather_than_inside_one() -> None:
    """Half a word is a mistake a reader notices; a model answers in words."""
    cut = truncated("anticonstitutionnellement et puis autre chose", 1)

    assert cut == "anticonstitutionnellement…"


def test_a_speech_is_split_into_the_bubbles_it_will_be_shown_as() -> None:
    """One sentence per bubble (D-018), decided on the server so a replay matches (D-023)."""
    said = "Théo, tu m'accuses. Hier tu n'as rien dit ! Pourquoi ?"

    assert sentences(said) == ("Théo, tu m'accuses.", "Hier tu n'as rien dit !", "Pourquoi ?")


def test_a_single_sentence_is_a_single_bubble() -> None:
    assert sentences("Je vous écoute.") == ("Je vous écoute.",)


def test_splitting_the_same_speech_twice_gives_the_same_bubbles() -> None:
    """Determinism is the whole point of doing it here rather than in a browser."""
    said = "Un. Deux… Trois ! Quatre ?"

    assert sentences(said) == sentences(said)
