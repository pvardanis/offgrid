"""LM Studio, which serves Anthropic's message API alongside OpenAI's."""

import httpx

from offgrid.dialect import Dialect
from offgrid.exceptions import RuntimeUnreachableError
from offgrid.model import Model

CATALOGUE = "/api/v0/models"
MESSAGES = "/v1/messages"
TIMEOUT_SECONDS = 5

# Weights come off disk at gigabytes a second, so a large model takes tens of
# seconds and a cold cache takes longer.
LOAD_TIMEOUT_SECONDS = 300


def dialect() -> Dialect:
    """Report the API shape LM Studio serves.

    :return: The Anthropic dialect, which needs no translation for Claude Code.
    """
    return Dialect.ANTHROPIC


def parse_models(payload: dict) -> list[Model]:
    """Read the catalogue into models that can be sized and ranked.

    :param payload: A decoded response from the catalogue endpoint.

    :return: Every model that generates text, embeddings excluded.

    :raise RuntimeUnreachableError: When the body is not a catalogue. A
        server that answers with something else has not told us it holds no
        models, and reporting an empty list would say that it did.
    """
    if "data" not in payload:
        raise RuntimeUnreachableError(
            f"The body at {CATALOGUE} is not a catalogue: it has no 'data', only "
            f"{sorted(payload) or 'nothing'}. Check the address points at LM Studio."
        )

    models = []
    for entry in payload["data"]:
        if entry.get("type") == "embeddings":
            continue

        identifier = entry.get("id")
        if not identifier:
            raise RuntimeUnreachableError(
                f"The catalogue at {CATALOGUE} lists a model with no id. "
                "Update LM Studio, or report the response it gave."
            )

        models.append(
            Model(
                identifier=identifier,
                context_limit=entry.get("loaded_context_length")
                or entry.get("max_context_length")
                or 0,
            )
        )

    return models


def resident(payload: dict) -> Model | None:
    """Find a model already held in memory.

    Loading a model costs the wait for its weights and the prompt prefix
    cached against whatever was there before, so a resident model is the
    cheap choice.

    :param payload: A decoded response from the catalogue endpoint.

    :return: The first loaded model in catalogue order, or ``None`` when the
        server holds none. LM Studio can hold several at once; which of them
        answers is decided by the request, not by this.
    """
    loaded = {
        entry["id"]
        for entry in payload.get("data", [])
        if entry.get("state") == "loaded"
    }

    return next((m for m in parse_models(payload) if m.identifier in loaded), None)


def catalogue(host: str) -> dict:
    """Fetch the runtime's catalogue.

    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.

    :return: The decoded response.

    :raise RuntimeUnreachableError: When nothing answers, when the answer
        takes too long, or when what comes back is not a catalogue. Each case
        says which it was: a server that answered with a 500 is running, and
        being told to start it sends you looking in the wrong place.
    """
    url = f"http://{host}{CATALOGUE}"

    try:
        response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    except httpx.TimeoutException as error:
        raise RuntimeUnreachableError(
            f"http://{host} did not answer within {TIMEOUT_SECONDS}s. "
            "It may be loading a model; try again once it settles."
        ) from error
    except httpx.TransportError as error:
        raise RuntimeUnreachableError(
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"{url} answered {response.status_code}. The server is running but "
            "served no catalogue; check its local server is enabled."
        )

    try:
        return response.json()
    except ValueError as error:
        raise RuntimeUnreachableError(
            f"{url} answered with {response.headers.get('content-type', 'no type')}, "
            f"not JSON. Is http://{host} really LM Studio?"
        ) from error


def load(host: str, identifier: str, timeout: float = LOAD_TIMEOUT_SECONDS) -> None:
    """Hold a model in memory, waiting until it is ready to answer.

    Asking for a single token is what makes the runtime load it. Doing that
    here rather than leaving it to the first real request means the wait is
    visible and attributable, instead of a silence in the middle of a turn.

    :param host: Address the runtime listens on.
    :param identifier: The model to load.
    :param timeout: How long to wait before giving up.

    :raise RuntimeUnreachableError: When the load does not finish in time, or
        the runtime refuses it.
    """
    url = f"http://{host}{MESSAGES}"
    body = {
        "model": identifier,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }

    try:
        response = httpx.post(url, json=body, timeout=timeout)
    except httpx.TimeoutException as error:
        raise RuntimeUnreachableError(
            f"{identifier} did not finish loading within {timeout:.0f}s. "
            "Load it in the runtime directly, or allow longer."
        ) from error
    except httpx.TransportError as error:
        raise RuntimeUnreachableError(
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"The runtime answered {response.status_code} loading {identifier}. "
            "Check the name against `offgrid doctor`, and that it has room."
        )
