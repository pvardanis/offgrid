"""What onyx.app serves today, as against what it served when it was captured.

Opt-in, with `uv run pytest -m live`. Everything else about the parser runs
against a fixture, which cannot notice the page being redesigned — and the
payload is one that onyx documents nowhere and owes nobody. This is the check
that reports it.
"""

import pytest

from offgrid.exceptions import OffgridError
from offgrid.leaderboards.onyx import fetch, parse

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
