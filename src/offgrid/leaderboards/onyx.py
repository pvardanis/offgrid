"""onyx.app's coding leaderboard, and what it takes to read one row of it.

The page states no API, and renders its table into the React payload its own
front end is built from. Every locator here is therefore a name out of
someone else's source code. `docs/research/onyx-leaderboard.md` records what
was established about it, and when.
"""

import json

import httpx

from offgrid.exceptions import LeaderboardUnavailableError
from offgrid.listing import Listing, Table

URL = "https://onyx.app/best-llm-for-coding"

# The route answers a request carrying this with the flight text and no HTML
# around it. A Next.js convention, not an interface onyx states.
FLIGHT = {"RSC": "1"}

TIMEOUT_SECONDS = 10

# The prop name the page component is called with, where the table starts.
TABLE = '"config":{'

# Sizes are published as strings — "35B", "1.6T" — so the suffix says how many.
SCALES = {"M": 1e6, "B": 1e9, "T": 1e12}


def parse(flight: str) -> Table:
    """Read the table out of the page's own payload.

    :param flight: The React payload the page is rendered from.

    :return: The table, holding every model published with a size.

    :raise LeaderboardUnavailableError: When the table is not where it was,
        or is not shaped like a table. A silent empty list would read as
        "nothing fits this machine", which is a different claim entirely.
    """
    start = flight.find(TABLE)
    if start < 0:
        raise _unreadable(f"is gone: nothing in the page holds {TABLE} any more")

    try:
        config, _ = json.JSONDecoder().raw_decode(flight, start + len('"config":'))
    except ValueError as error:
        raise _unreadable(f"starts where it did and is not JSON: {error}") from error

    models = config.get("models")
    if not isinstance(models, list):
        raise _unreadable(f"has no list of models, only {sorted(config)}")

    listings = _listings(models)
    if not listings:
        raise _unreadable(
            f"lists {len(models)} models and states a size for none of them"
        )

    return Table(dated=config.get("lastUpdated"), listings=listings)


def fetch() -> str:
    """Ask onyx for the page the table is rendered into.

    :return: The flight text, undecoded.

    :raise LeaderboardUnavailableError: When nothing answers, when the answer
        takes too long, or when it is not a page. The machine is measured
        without a network, and a failure here says nothing about it.
    """
    try:
        response = httpx.get(
            URL, headers=FLIGHT, timeout=TIMEOUT_SECONDS, follow_redirects=True
        )
    except httpx.TimeoutException as error:
        raise LeaderboardUnavailableError(
            f"{URL} did not answer within {TIMEOUT_SECONDS}s. "
            "Try again, or read docs/models.md for what was measured here."
        ) from error
    except httpx.RequestError as error:
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


def _unreadable(complaint: str) -> LeaderboardUnavailableError:
    """Say the table could not be read, and where to look instead.

    :param complaint: What was wrong with it.

    :return: The error to raise. Every one of these is onyx redesigning a
        page they document to nobody, so each says to go and read it.
    """
    return LeaderboardUnavailableError(
        f"The table at {URL} {complaint}. Read {URL} by hand."
    )


def _listings(models: list) -> list[Listing]:
    """Keep the models a machine can be measured against.

    :param models: The table's rows, as published.

    :return: One listing per row stating a parameter count. A row without
        one cannot be sized, which is every closed model.
    """
    listings = []
    for model in models:
        if not isinstance(model, dict):
            continue

        parameters = _parameters(model.get("parameters"))
        if parameters is None:
            continue

        listings.append(
            Listing(
                name=model.get("name") or "unnamed",
                parameters=parameters,
                context_window=model.get("contextWindow"),
                license=(model.get("operational") or {}).get("license"),
            )
        )

    return listings


def _parameters(published: str | None) -> float | None:
    """Read a parameter count out of the way the table writes one.

    :param published: What the row states, e.g. ``"35B"``. ``"N/A"`` is how
        the table writes a size it does not publish, and null is how it
        writes the same thing for a closed model.

    :return: The count, or ``None`` when the row states no size.
    """
    if not isinstance(published, str):
        return None

    size = published.strip()
    scale = SCALES.get(size[-1:].upper())

    try:
        return float(size[:-1]) * scale if scale else None
    except ValueError:
        return None
