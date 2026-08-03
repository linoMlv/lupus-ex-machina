"""Errors raised by the engine.

They all carry a human-readable reason: an illegal intent is expected to happen
routinely once language models drive the agents, and the reason is what makes
those refusals diagnosable.
"""


class EngineError(Exception):
    """Base class for every engine refusal."""


class IllegalTransitionError(EngineError):
    """A phase change the state machine does not allow."""


class IllegalIntentError(EngineError):
    """An intent the current state does not allow."""
