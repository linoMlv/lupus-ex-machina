"""The token a session cookie carries (J8.1, D-098).

Signed rather than stored: there is one user and one thing to remember — that
they got the password right — so a server-side session table would be state to
keep in step with nothing. What the cookie holds is an expiry and a signature
over it, and a cookie nobody signed is worth exactly as much as no cookie.

Everything here is stdlib. A signing library for one HMAC would be a dependency
carrying a line of code.
"""

from datetime import UTC, datetime, timedelta

from lupus_ex_machina.api.session import SESSION_LIFETIME, minted, valid

KEY = "clef-de-signature"
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_a_token_this_key_minted_is_accepted_by_this_key() -> None:
    assert valid(minted(KEY, at=NOW), KEY, at=NOW)


def test_a_token_signed_with_another_key_is_refused() -> None:
    """The whole point of signing: a cookie a browser made up is worth nothing."""
    assert not valid(minted("une-autre-clef", at=NOW), KEY, at=NOW)


def test_a_token_whose_signature_was_touched_is_refused() -> None:
    token = minted(KEY, at=NOW)

    assert not valid(token[:-1] + ("0" if token.endswith("1") else "1"), KEY, at=NOW)


def test_a_token_whose_expiry_was_pushed_back_is_refused() -> None:
    """Tampering with the payload has to break the signature, or it is decoration."""
    expiry, signature = minted(KEY, at=NOW).split(".", 1)
    forged = f"{int(expiry) + 10_000}.{signature}"

    assert not valid(forged, KEY, at=NOW)


def test_a_token_is_refused_once_it_has_expired() -> None:
    token = minted(KEY, at=NOW)

    assert not valid(token, KEY, at=NOW + SESSION_LIFETIME + timedelta(seconds=1))


def test_a_token_lasts_the_whole_lifetime() -> None:
    token = minted(KEY, at=NOW)

    assert valid(token, KEY, at=NOW + SESSION_LIFETIME - timedelta(seconds=1))


def test_something_that_is_not_a_token_at_all_is_refused() -> None:
    """A cookie is whatever the client sends; none of it may raise."""
    assert not valid("", KEY, at=NOW)
    assert not valid("pas-un-jeton", KEY, at=NOW)
    assert not valid("plus.tard.encore", KEY, at=NOW)
