"""The request one completion is, as the OpenAI protocol describes it (D-043).

Its own module rather than a private method of the client, because **two callers
must send the same thing**: the client that plays the game, and the probe that
asks a provider whether it can play at all (D-115). A probe that built its own
body would be checking a request nobody ever sends — the shape of defect this
project meets most often, two components meant to say the same thing.

The schema travels with every request and is marked strict (D-035). Pydantic
still validates the answer: a perfectly valid JSON can ask to vote for a dead
player, and the engine remains the last authority on that (D-001).
"""

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from lupus_ex_machina.llm.messages import Message


def completion_body(
    *,
    model: str,
    messages: Sequence[Message],
    schema: type[BaseModel],
    temperature: float = 1.0,
    top_p: float = 1.0,
) -> dict[str, Any]:
    """One completion request, schema and all."""
    return {
        "model": model,
        "messages": [json.loads(message.model_dump_json()) for message in messages],
        "temperature": temperature,
        "top_p": top_p,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        },
    }
