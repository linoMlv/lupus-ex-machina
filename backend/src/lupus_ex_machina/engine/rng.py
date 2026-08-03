"""The single source of randomness.

Every draw in the engine — dealing roles, breaking ties, scripted agents — goes
through a generator built here from one seed. This is the only module of the
package allowed to import :mod:`random`, which an architecture test enforces:
a stray ``random.choice`` anywhere else would silently destroy reproducibility
and turn failing tests into unrepeatable ones.
"""

from random import Random

Rng = Random


def create_rng(seed: int) -> Rng:
    """Build the generator a whole game draws from."""
    return Random(seed)
