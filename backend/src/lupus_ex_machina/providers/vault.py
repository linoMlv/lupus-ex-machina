"""Keeping a provider key unreadable at rest (D-113).

Fernet, from ``cryptography``: authenticated encryption, so a key that has been
tampered with is refused rather than silently decrypted into nonsense. Writing
one's own would be the worst idea in the project.

**The secret is ``LUPUS_SECRET_KEY``**, the same variable that signs the session
cookie — and the same variable carries two different demands, which is the part
worth remembering. D-098 lets the cookie do without it: absent, a key is drawn at
start-up and everyone is logged out on a restart, which costs nothing. A registry
encrypted under a drawn key would be **unreadable** at the next restart, so
D-113 refuses to register a key without a supplied secret.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _keyed(secret: str) -> bytes:
    """The Fernet key that secret stands for.

    Fernet takes thirty-two bytes in url-safe base64, and a secret is a
    passphrase of any length — so it is hashed into that shape rather than
    trusted to already be it.

    SHA-256 is a *derivation* here, not a password hash. What it stands in front
    of is high-entropy and read from the environment, never guessed at, so the
    slow hashes that protect a chosen password would buy nothing.
    """
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


class UnreadableSecretError(Exception):
    """A stored key that this secret cannot open.

    Almost always one thing: ``LUPUS_SECRET_KEY`` has changed since the key was
    stored. Said out loud rather than swallowed, because the symptom otherwise
    looks like the provider rejecting a perfectly good key.
    """


def sealed(clear: str, *, secret: str) -> str:
    """That key, unreadable to anybody without the secret."""
    return Fernet(_keyed(secret)).encrypt(clear.encode("utf-8")).decode("ascii")


def opened(sealed_key: str, *, secret: str) -> str:
    """That key back, or a refusal saying why it cannot be read."""
    try:
        return Fernet(_keyed(secret)).decrypt(sealed_key.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as unreadable:
        raise UnreadableSecretError(
            "Cette clé a été chiffrée avec un autre secret. "
            "Vérifiez LUPUS_SECRET_KEY, ou ressaisissez la clé du fournisseur."
        ) from unreadable
