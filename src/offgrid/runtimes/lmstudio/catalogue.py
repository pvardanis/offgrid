"""What LM Studio has, and what it is holding.

One payload answers both, which is LM Studio's own efficiency: the fetch
below gets it and the two readers say what it means. A runtime that answered
the two questions from two endpoints would fetch twice.

Why a call did not arrive is a table per call, so the three sentences read
beside each other rather than down a ladder of `except` branches.
"""

import httpx

from offgrid.domain.model import Model
from offgrid.shared.exceptions import RuntimeUnreachableError

CATALOGUE = "/api/v0/models"
TIMEOUT_SECONDS = 5


def get_catalogue_payload(host: str) -> dict:
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
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            _explain_why_the_catalogue_did_not_arrive(error, host=host, url=url)
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


def parse_models_from_payload(payload: dict) -> list[Model]:
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


def get_loaded_models(payload: dict) -> list[Model]:
    """Find every model held in memory.

    The machine has one pool of memory, and LM Studio can hold several models
    in it at once, so what is held is a list rather than a single answer.

    :param payload: A decoded response from the catalogue endpoint.

    :return: Every loaded model, in catalogue order, described by the context
        the runtime serves it at rather than its ceiling.
    """
    # Read through `parse_models` rather than the payload, so an entry with
    # no id is the error it names rather than a `KeyError` from in here.
    held = {
        entry.get("id")
        for entry in payload.get("data", [])
        if entry.get("state") == "loaded"
    }

    return [
        model
        for model in parse_models_from_payload(payload)
        if model.identifier in held
    ]


def _explain_why_the_catalogue_did_not_arrive(
    error: httpx.RequestError, *, host: str, url: str
) -> str:
    """Say which way the call failed, and what to do about that one.

    :param error: What httpx raised.
    :param host: Address the runtime was expected on.
    :param url: What was asked for.

    :return: What to tell whoever ran offgrid.
    """
    # Most specific first: a `TimeoutException` is a `TransportError`, which is
    # a `RequestError`, so the first that matches is the one that fits.
    said = {
        httpx.TimeoutException: (
            f"http://{host} did not answer within {TIMEOUT_SECONDS}s. "
            "It may be loading a model; try again once it settles."
        ),
        httpx.TransportError: (
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ),
        httpx.RequestError: (
            f"The answer from {url} could not be read: {error}. Something is "
            f"listening at http://{host}; check it is LM Studio's local server."
        ),
    }

    return next(sentence for kind, sentence in said.items() if isinstance(error, kind))
