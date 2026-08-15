"""Whether a model honours a strict JSON schema, and the three ways of failing.

D-115, and the heart of J8bis: **a failed probe does not prove an
incompatibility**. Telling "the API will not take this parameter" apart from
"the network dropped" is what keeps a perfectly good provider from being
rejected over a bad minute — and a probe that concludes from nothing is the
failure this project has already met five times.
"""

import json

import httpx2

from lupus_ex_machina.providers.compatibility import probed
from lupus_ex_machina.providers.verdicts import Verdict
from support.providers import API_KEY, MISTRAL, completing, failing, refusing

ANSWERED_WELL = json.dumps({"understood": True})


async def test_a_model_that_answers_in_the_shape_it_was_asked_for_is_compatible() -> None:
    verdict = await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=completing(ANSWERED_WELL),
    )

    assert verdict is Verdict.COMPATIBLE


async def test_a_provider_that_names_the_parameter_it_refuses_is_a_refusal() -> None:
    """The one observation that closes the question: the API says so itself."""
    verdict = await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=refusing(400, saying="response_format json_schema is not supported"),
    )

    assert verdict is Verdict.REFUSED


async def test_an_answer_that_ignores_the_schema_asks_for_confirmation() -> None:
    """The provider took the parameter and answered something else.

    Not a refusal — it accepted the request — and not a compatibility either.
    Whether to play on it is the owner's call, so the probe says exactly that
    (D-115).
    """
    verdict = await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=completing(json.dumps({"whatever": "not the shape asked for"})),
    )

    assert verdict is Verdict.NEEDS_CONFIRMATION


async def test_a_four_hundred_that_names_nothing_is_not_a_refusal() -> None:
    """The trap of D-115, and the reason the refusal has to be explicit.

    A four hundred can be a malformed request, an unknown model, a provider
    having a bad day. Reading it as "this provider cannot play" would throw away
    a good one for a reason nobody ever stated.
    """
    verdict = await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=refusing(400, saying="something went wrong"),
    )

    assert verdict is Verdict.UNKNOWN


async def test_a_refused_key_teaches_nothing_about_the_schema() -> None:
    verdict = await probed(
        "mistral-small-latest", base_url=MISTRAL, api_key=API_KEY, transport=refusing(401)
    )

    assert verdict is Verdict.UNKNOWN


async def test_a_spent_quota_teaches_nothing_either() -> None:
    """The most ordinary answer of all on a free tier.

    And one that says nothing whatsoever about schemas.
    """
    verdict = await probed(
        "mistral-small-latest", base_url=MISTRAL, api_key=API_KEY, transport=refusing(429)
    )

    assert verdict is Verdict.UNKNOWN


async def test_a_provider_that_never_answered_teaches_nothing() -> None:
    verdict = await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=failing(httpx2.ConnectError("nowhere to connect")),
    )

    assert verdict is Verdict.UNKNOWN


async def test_an_answer_that_is_not_a_completion_teaches_nothing() -> None:
    """A 200 that carries something else entirely.

    The probe learnt nothing about the schema, so it says so rather than blaming
    the model.
    """
    serving_a_page = httpx2.MockTransport(
        lambda request: httpx2.Response(200, html="<html><body>Bienvenue</body></html>")
    )

    verdict = await probed(
        "mistral-small-latest", base_url=MISTRAL, api_key=API_KEY, transport=serving_a_page
    )

    assert verdict is Verdict.UNKNOWN


async def test_a_failed_request_is_never_read_as_a_good_answer() -> None:
    """A body is only worth reading when the request it answers succeeded.

    Gateways and proxies do serve error statuses with a body attached; taking
    one for a completion would report a model as compatible on the strength of
    a request that failed.
    """
    failing_with_a_body = httpx2.MockTransport(
        lambda request: httpx2.Response(
            502, json={"choices": [{"message": {"content": ANSWERED_WELL}}]}
        )
    )

    verdict = await probed(
        "mistral-small-latest", base_url=MISTRAL, api_key=API_KEY, transport=failing_with_a_body
    )

    assert verdict is Verdict.UNKNOWN


async def test_the_probe_sends_the_very_request_a_game_sends() -> None:
    """Otherwise it would be checking a request nobody ever sends.

    The strict JSON schema is the whole subject of the probe (D-035), so the
    body is built by the same code the client builds its own with.
    """
    seen: list[httpx2.Request] = []

    await probed(
        "mistral-small-latest",
        base_url=MISTRAL,
        api_key=API_KEY,
        transport=completing(ANSWERED_WELL, seen=seen),
    )

    (asked,) = seen
    assert asked.method == "POST"
    assert str(asked.url) == f"{MISTRAL}/chat/completions"
    body = json.loads(asked.content)
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["model"] == "mistral-small-latest"
