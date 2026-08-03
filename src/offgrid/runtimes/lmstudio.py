"""LM Studio, which serves Anthropic's message API alongside OpenAI's.

The catalogue endpoint reports quantization, context and residency, but no
parameter counts, so sizes are read from each identifier by
``offgrid.naming``.
"""

import re

import httpx

from offgrid.dialect import Dialect
from offgrid.exceptions import RuntimeUnreachableError
from offgrid.model import Model
from offgrid.naming import parameter_counts

CATALOGUE = "/api/v0/models"
TIMEOUT_SECONDS = 5
# Unquantized MLX and GGUF weights are 16-bit; assume that when unstated.
DEFAULT_BITS = 16


def dialect() -> Dialect:
    """Report the API shape LM Studio serves.

    :return: The Anthropic dialect, which needs no translation for Claude Code.
    """
    return Dialect.ANTHROPIC


def _bits(quantization: str | None) -> int:
    """Read a bit width from LM Studio's quantization label.

    :param quantization: An MLX label such as ``4bit``, a GGUF one such as
        ``Q4_K_M`` or ``Q8_0``, an unquantized one such as ``BF16``, or
        ``None`` when the catalogue states none.

    :return: Bits per parameter. Only the first run of digits is the width:
        the ``0`` in ``Q8_0`` names a variant, and reading it as part of the
        number sizes an eight billion parameter model at eighty billion.
    """
    if not quantization:
        return DEFAULT_BITS
    found = re.search(r"\d+", quantization)
    return int(found.group()) if found else DEFAULT_BITS


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
        total, active = parameter_counts(identifier)
        models.append(
            Model(
                identifier=identifier,
                parameters=total,
                active_parameters=active,
                quantization_bits=_bits(entry.get("quantization")),
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
