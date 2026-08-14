"""What onyx.app serves today, as against what it served when it was captured.

Opt-in, with `uv run pytest -m live`. Everything else about the parser runs
against a fixture, which cannot notice the page being redesigned — and the
payload is one that onyx documents nowhere and owes nobody. This is the check
that reports it.
"""

import pytest

from offgrid.leaderboards.onyx import fetch, parse
from offgrid.shared.exceptions import OffgridError

pytestmark = pytest.mark.live


def test_the_published_table_is_still_where_the_parser_looks():
    try:
        flight = fetch()
    except OffgridError as error:
        pytest.skip(f"no leaderboard answering: {error}")

    table = parse(flight)

    assert table.dated
    assert table.listings
    assert all(listing.parameters > 0 for listing in table.listings)


def test_the_keys_the_ranking_reads_are_still_the_keys_the_table_writes():
    # Renaming either of these leaves a table that parses into listings with
    # nothing to rank them by, and `recommend` prints an empty shortlist
    # rather than saying anything went wrong.
    try:
        listings = parse(fetch()).listings
    except OffgridError as error:
        pytest.skip(f"no leaderboard answering: {error}")

    assert any(listing.coding_score for listing in listings)
    assert any(listing.active_parameters for listing in listings)
