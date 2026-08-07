"""onyx.app's coding leaderboard, and what it takes to read one row of it.

The page states no API. It renders the table into the React payload its own
front end is built from, so that payload is what offgrid reads, and every
locator here is a name from someone else's source code rather than a
documented interface. `docs/research/onyx-leaderboard.md` records what was
established about it, and when.
"""

import json

import httpx

from offgrid.exceptions import LeaderboardUnavailableError
from offgrid.listing import Listing, Table

URL = "https://onyx.app/best-llm-for-coding"

# The route answers a request carrying this with the flight text alone, and
# no HTML around it. A Next.js convention, not an interface onyx states.
FLIGHT = {"RSC": "1"}

TIMEOUT_SECONDS = 10

# The prop name the page component is called with, which is where the table
# starts. One rename inside onyx and this is gone.
TABLE = '"config":{'

# Parameter counts are published as strings — "35B", "1.6T" — so the suffix
# is what says how many.
SCALES = {"M": 1e6, "B": 1e9, "T": 1e12}


def parse(flight: str) -> Table:
    """Read the table out of the page's own payload.

    :param flight: The React payload the page is rendered from.

    :return: The table, holding every model published with a size.

    :raise LeaderboardUnavailableError: When the table is not where it was,
        or is not shaped like a table. onyx can redesign the page whenever
        it likes, and a silent empty list would read as "nothing fits".
    """
    start = flight.find(TABLE)
    if start < 0:
        raise LeaderboardUnavailableError(
            f"{URL} answered with no {TABLE} in it, which is where its table "
            f"was. The page has been redesigned; read {URL} by hand."
        )

    try:
        config, _ = json.JSONDecoder().raw_decode(flight, start + len('"config":'))
    except ValueError as error:
        raise LeaderboardUnavailableError(
            f"The table at {URL} starts where it did and is not JSON: {error}. "
            f"Read {URL} by hand."
        ) from error

    models = config.get("models")
    if not isinstance(models, list):
        raise LeaderboardUnavailableError(
            f"The table at {URL} has no list of models, only {sorted(config)}. "
            f"Read {URL} by hand."
        )

    return Table(dated=config.get("lastUpdated"), listings=_listings(models))


def fetch() -> str:
    """Ask onyx for the page the table is rendered into.

    :return: The flight text, undecoded.

    :raise LeaderboardUnavailableError: When nothing answers, when the answer
        takes too long, or when it is not a page. The machine is measured
        without a network, and a failure here says nothing about it.
    """
    try:
        response = httpx.get(URL, headers=FLIGHT, timeout=TIMEOUT_SECONDS)
    except httpx.TimeoutException as error:
        raise LeaderboardUnavailableError(
            f"{URL} did not answer within {TIMEOUT_SECONDS}s. "
            "Try again, or read docs/models.md for what was measured here."
        ) from error
    except httpx.TransportError as error:
        raise LeaderboardUnavailableError(
            f"Could not reach {URL}: {error}. This is the one command that "
            "needs a network; the rest of offgrid does not."
        ) from error

    if response.is_error:
        raise LeaderboardUnavailableError(
            f"{URL} answered {response.status_code} rather than its table. "
            "Try again later, or read docs/models.md."
        )

    return response.text


def _listings(models: list) -> list[Listing]:
    """Keep the models a machine can be measured against.

    :param models: The table's rows, as published.

    :return: One listing per row stating a parameter count. A row without one
        cannot be sized, which is every closed model and needs no licence
        logic to see.
    """
    listings = []
    for model in models:
        parameters = _parameters(model.get("parameters"))
        if parameters is None:
            continue

        listings.append(
            Listing(
                name=model.get("name", "unnamed"),
                parameters=parameters,
                context_window=model.get("contextWindow"),
                license=model.get("operational", {}).get("license"),
            )
        )

    return listings


def _parameters(published: str | None) -> float | None:
    """Read a parameter count out of the way the table writes one.

    :param published: What the row states, e.g. ``"35B"``. ``"N/A"`` is how
        the table says a model's size is not published, and null is how it
        says the same thing for a closed one.

    :return: The count, or ``None`` when the row states no size.
    """
    if not isinstance(published, str):
        return None

    scale = SCALES.get(published.strip()[-1:].upper())
    if scale is None:
        return None

    try:
        return float(published.strip()[:-1]) * scale
    except ValueError:
        return None
