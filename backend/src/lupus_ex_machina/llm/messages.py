"""The messages a conversation with a model is made of.

Their own module because both the client and the fake provider need them, and
neither should have to import the other.

Contents are French, because they are read by the models; everything around them
is English (HR-6).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """Who a message in a conversation comes from."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """One message of the conversation handed to a model."""

    model_config = ConfigDict(frozen=True)

    role: Role
    content: str
