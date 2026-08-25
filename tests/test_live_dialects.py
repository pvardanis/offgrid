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

from offgrid.cli.binding import read_profile
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.running.dialect import Dialect
from offgrid.runtimes.lmstudio.serving import DIALECTS
from offgrid.shared.exceptions import OffgridError

pytestmark = pytest.mark.live

ASK = {"model": "nothing-is-held", "messages": [], "max_tokens": 1}


@pytest.fixture
def host() -> str:
    """Where the runtime listens, as the stored profile says.

    :return: The address from the profile.
    """
    try:
        return read_profile(DEFAULT_PATH).runtime.host
    except OffgridError as error:
        pytest.skip(f"no profile to read the runtime's address from: {error}")


def _refusal(host: str, endpoint: str) -> dict:
    """Ask an endpoint for something it will refuse, and read the refusal.

    A refusal is the cheapest proof that an endpoint is implemented, and the
    body is the only place it shows. An endpoint LM Studio does not have is
    not a 404: it answers 200 with its own catch-all, `Unexpected endpoint or
    method`. So the status says nothing and the shape says everything — a body
    shaped the way a dialect shapes it is that dialect answering.

    :param host: Where the runtime listens.
    :param endpoint: The path to ask.

    :return: What came back, parsed.
    """
    try:
        answered = httpx.post(f"http://{host}{endpoint}", json=ASK, timeout=30)
    except httpx.HTTPError as error:
        pytest.skip(f"no runtime answering at {host}: {error}")

    return answered.json()


def test_the_openai_endpoint_answers_in_the_openai_shape(host: str):
    assert Dialect.OPENAI in DIALECTS

    refusal = _refusal(host, "/v1/chat/completions")

    # This endpoint carries the complaint under `error` and tags nothing else,
    # where the Anthropic one tags the body as an error and nests a typed one
    # inside. Asserting the shape rather than the status is what tells the two
    # apart on a server that serves both — and the tag is the whole of the
    # difference, since LM Studio answers here with a bare string rather than
    # the object naming a parameter that OpenAI's own service returns.
    assert refusal["error"]
    assert "type" not in refusal


def test_the_anthropic_endpoint_answers_in_the_anthropic_shape(host: str):
    assert Dialect.ANTHROPIC in DIALECTS

    refusal = _refusal(host, "/v1/messages")

    assert refusal["type"] == "error"
    assert refusal["error"]["type"]
