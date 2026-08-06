"""What can go wrong between the project and a model."""


class ModelAnswerError(RuntimeError):
    """A model never produced an answer of the shape it was asked for."""


class ThrottledError(RuntimeError):
    """A provider kept refusing for rate reasons until the attempts ran out."""
