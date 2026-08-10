"""The token a session cookie carries, and what makes it worth trusting (D-098).

Signed, not stored. There is one user and one thing to remember about them —
that they got the password right — so a table of sessions on the server would be
state kept in step with nothing, and J8 has already decided against parallel
state: the journal is the only thing a reconnection needs.

The token is an expiry and a signature over it. Tampering with the expiry breaks
the signature, an unsigned cookie is worth exactly as much as no cookie, and a
signature is compared in constant time like the password it stands for.

Everything here is stdlib: a signing library for one HMAC would be a dependency
carrying a single line of code.
"""

import hashlib
import hmac
from datetime import datetime, timedelta

#: How long a session lasts. Long, because the alternative is asking the one
#: user of a private application for a password they set themselves.
SESSION_LIFETIME = timedelta(days=30)

#: Name of the cookie the token travels in.
SESSION_COOKIE = "lupus_session"

ENCODING = "utf-8"


def minted(key: str, *, at: datetime) -> str:
    """A token valid for the lifetime that starts at that instant.

    The instant is passed rather than read from a clock: a session that could
    only be tested by waiting a month could not be tested at all.
    """
    expiry = int((at + SESSION_LIFETIME).timestamp())
    return f"{expiry}.{_signature(expiry, key)}"


def valid(token: str, key: str, *, at: datetime) -> bool:
    """Whether that token was signed with this key and has not run out.

    Anything the client sends arrives here, so nothing about a malformed token
    may raise: a cookie that is not a token is simply not a session.
    """
    expiry, _, signature = token.partition(".")
    try:
        deadline = int(expiry)
    except ValueError:
        return False

    if not hmac.compare_digest(signature, _signature(deadline, key)):
        return False
    return at.timestamp() < deadline


def _signature(expiry: int, key: str) -> str:
    """The signature this key gives that expiry."""
    return hmac.new(key.encode(ENCODING), str(expiry).encode(ENCODING), hashlib.sha256).hexdigest()
