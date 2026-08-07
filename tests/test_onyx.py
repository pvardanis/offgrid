"""What the published table parses into.

The fixture is the flight text `curl -H 'RSC: 1'` returned on 2026-08-07, kept
verbatim but for two things the parse never reads: the PostHog identifier onyx
minted for that fetch, which is zeroed, and their chat widget's cloud API key,
which is replaced. Both are theirs and public, and neither is part of the
table; committing credential material trips a secret scanner besides.
"""

import pathlib

import pytest

from offgrid.leaderboards.onyx import parse

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "onyx_leaderboard.txt"


@pytest.fixture(scope="session")
def flight() -> str:
    return FIXTURE.read_text()


def test_the_table_is_found_in_the_flight_text(flight: str):
    table = parse(flight)

    assert table.dated == "2026-07-20"
    assert "Qwen3.6-35B-A3B" in [listing.name for listing in table.listings]


def test_a_model_published_with_no_size_is_not_listed(flight: str):
    # Which is every closed model on the table, arrived at without reading a
    # single licence: nobody publishes the parameter count of a model you
    # cannot download.
    names = [listing.name for listing in parse(flight).listings]

    assert "Claude Opus 4.8" not in names
    assert "GPT-5.6 Sol" not in names
    assert "DeepSeek-V4-Pro" in names


def test_a_size_the_table_writes_as_unavailable_is_not_a_size(flight: str):
    names = [listing.name for listing in parse(flight).listings]

    assert "Gemini 3.1 Pro" not in names
    assert "Grok 3" not in names


def test_a_size_written_as_a_string_is_read_as_a_number(flight: str):
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Qwen3.6-35B-A3B"].parameters == 35e9
    assert by_name["DeepSeek-V4-Pro"].parameters == 1.6e12


def test_the_context_window_is_carried_as_published(flight: str):
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Qwen3.6-27B"].context_window == 262144


def test_the_licence_is_carried_however_it_is_written(flight: str):
    # It is a date on one open-weight row and absent on another, which is why
    # nothing offgrid does reads it.
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Kimi K3"].license == "Open weights 2026-07-27"
    assert by_name["DeepSeek V3.2"].license is None
    assert by_name["Qwen3.6-27B"].license == "Apache 2.0"
