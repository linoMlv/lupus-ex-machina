"""What a compatibility probe can conclude about one model (D-115).

Its own module, small on purpose: the registry types what it keeps with it, and
the probe produces it. Putting the enumeration with the probe would have the
registry importing the network to name a value it merely stores.
"""

from enum import StrEnum


class Verdict(StrEnum):
    """What a probe of one model concluded."""

    COMPATIBLE = "compatible"
    """It answered in the shape it was asked for. It can play."""

    REFUSED = "refused"
    """The provider itself said it will not take a strict JSON schema.

    The one observation that closes the question, because it comes from the only
    party in a position to state it.
    """

    NEEDS_CONFIRMATION = "needs_confirmation"
    """It took the request and answered something else.

    Neither a refusal nor a compatibility: whether to seat a model that ignores
    the shape it is given is the owner's call, not the project's (D-115).
    """

    UNKNOWN = "unknown"
    """Nothing was learnt — a refused key, a spent quota, a network that dropped.

    **Never written down.** A provider having a bad minute must not be condemned
    by it: the question is simply asked again another time (D-115).
    """
