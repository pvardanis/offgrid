"""LM Studio, which serves Anthropic's message API alongside OpenAI's.

The catalogue endpoint reports quantization, context and residency, but no
parameter counts, so sizes are read from each identifier by
``offgrid.naming``.
"""

import httpx

from offgrid.dialect import Dialect
from offgrid.exceptions import RuntimeUnreachableError
from offgrid.model import Model
from offgrid.naming import parameter_counts

CATALOGUE = "/api/v0/models"
TIMEOUT_SECONDS = 5
# Weights are stored at full precision unless the runtime says otherwise.
DEFAULT_BITS = 16


def dialect() -> Dialect:
    """Report the API shape LM Studio serves.

    :return: The Anthropic dialect, which needs no translation for Claude Code.
    """
    return Dialect.ANTHROPIC


def _bits(quantization: str | None) -> int:
    """Read a bit width from LM Studio's quantization label.

    :param quantization: A label such as ``4bit``, or ``None``.

    :return: Bits per parameter, defaulting to full precision.
    """
    if not quantization:
        return DEFAULT_BITS
    digits = "".join(c for c in quantization if c.isdigit())
    return int(digits) if digits else DEFAULT_BITS


def parse_models(payload: dict) -> list[Model]:
    """Read the catalogue into models that can be sized and ranked.

    :param payload: A decoded response from the catalogue endpoint.

    :return: Every model that generates text, embeddings excluded.
    """
    models = []
    for entry in payload.get("data", []):
        if entry.get("type") == "embeddings":
            continue
        total, active = parameter_counts(entry.get("id", ""))
        models.append(
            Model(
                identifier=entry["id"],
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
    """Find the model currently held in memory.

    Residency decides which model answers, because loading another evicts the
    cached prompt prefix along with the weights.

    :param payload: A decoded response from the catalogue endpoint.

    :return: The loaded model, or ``None`` when the server holds none.
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

    :raise RuntimeUnreachableError: When the server does not answer.
    """
    try:
        response = httpx.get(f"http://{host}{CATALOGUE}", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeUnreachableError(
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ) from error
    return response.json()
