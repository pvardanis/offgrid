"""What LM Studio serves today, as against the set the adapter states.

Opt-in, with `uv run pytest -m live`. `DIALECTS` widens what offgrid permits,
and a set that is wrong in that direction is expensive: the pair is accepted,
a load is paid for, and the agent fails on its own terms tens of seconds
later. Nothing that answers with a double can notice it — a double serves
whatever it was told to.

Neither check loads a model. An endpoint that is not there is what is being
asked about, and LM Studio answers that without holding anything.
"""

import httpx
import pytest

from offgrid.domain.running.dialect import Dialect
from offgrid.runtimes.lmstudio.serving import DIALECTS

pytestmark = pytest.mark.live

ASK = {"model": "nothing-is-held", "messages": [], "max_tokens": 1}

# What a path this server does not implement answers: 200, and a body carrying
# `Unexpected endpoint or method`. That is the same bare `error` string an
# implemented OpenAI endpoint refuses with, so the body alone cannot tell an
# endpoint that is there from one that is not — the refusal's status is what
# does, and both checks assert it.
REFUSED = 400


def _refusal(host: str, endpoint: str) -> httpx.Response:
    """Ask an endpoint for something it will refuse, and read the refusal.

    A refusal is the cheapest proof that an endpoint is implemented. What
    proves it is the pair of status and body: the catch-all answers 200 and
    the same shape as an OpenAI refusal, so a body shaped the way a dialect
    shapes it, answered with a refusing status, is that dialect answering.

    :param host: Where the runtime listens.
    :param endpoint: The path to ask.

    :return: What came back, unread.
    """
    try:
        return httpx.post(f"http://{host}{endpoint}", json=ASK, timeout=30)
    except httpx.HTTPError as error:
        pytest.skip(f"no runtime answering at {host}: {error}")


def test_the_openai_endpoint_answers_in_the_openai_shape(host: str):
    assert Dialect.OPENAI in DIALECTS

    answered = _refusal(host, "/v1/chat/completions")

    # Refused rather than caught: an endpoint LM Studio does not have answers
    # 200, whatever it puts in the body.
    assert answered.status_code == REFUSED
    # The complaint under `error`, and nothing tagging the body — where the
    # Anthropic endpoint tags it and nests a typed error inside. That is what
    # tells the two apart on a server serving both.
    assert answered.json()["error"]
    assert "type" not in answered.json()


def test_the_anthropic_endpoint_answers_in_the_anthropic_shape(host: str):
    assert Dialect.ANTHROPIC in DIALECTS

    answered = _refusal(host, "/v1/messages")

    assert answered.status_code == REFUSED
    refusal = answered.json()

    assert refusal["type"] == "error"
    assert refusal["error"]["type"]
