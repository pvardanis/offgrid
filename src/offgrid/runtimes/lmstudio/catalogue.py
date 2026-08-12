"""What LM Studio has, and what it is holding.

One payload answers both, which is LM Studio's own efficiency: `catalogue`
fetches it and the two readers below say what it means. A runtime that
answered the two questions from two endpoints would fetch twice.
"""

import httpx

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.model import Model

CATALOGUE = "/api/v0/models"
TIMEOUT_SECONDS = 5


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
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            f"The answer from {url} could not be read: {error}. Something is "
            f"listening at http://{host}; check it is LM Studio's local server."
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


def loaded(payload: dict) -> list[Model]:
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

    return [model for model in parse_models(payload) if model.identifier in held]
