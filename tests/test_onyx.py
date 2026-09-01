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


def test_the_table_says_where_it_was_read(flight: str):
    # Whoever prints it has to credit it, and the list itself is the only
    # thing that knows which list it is.
    assert parse(flight).source == "https://onyx.app/best-llm-for-coding"


def test_the_benchmark_the_list_ranks_by_is_carried_off_the_table(flight: str):
    # The list ranks by one of its twenty benchmarks, and the panel names which
    # one the figures came from, so the carried name is what it credits.
    assert parse(flight).benchmark == "swe_bench_verified"


def test_how_many_rows_stated_no_size_is_carried_off_the_table(flight: str):
    # A row dropped here is dropped before anything downstream sees it, so
    # the count is the only thing left to account for it with.
    table = parse(flight)

    assert table.unsized_rows == 9
    assert len(table.listings) == 18


def test_a_size_the_table_writes_as_unavailable_is_not_a_size(flight: str):
    names = [listing.name for listing in parse(flight).listings]

    assert "Gemini 3.1 Pro" not in names
    assert "Grok 3" not in names


def test_a_size_written_as_a_string_is_read_as_a_number(flight: str):
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Qwen3.6-35B-A3B"].parameters == 35e9
    assert by_name["DeepSeek-V4-Pro"].parameters == 1.6e12


def test_what_is_active_of_a_model_is_read_where_the_table_states_it(flight: str):
    # The table states it for a mixture and states it again as the whole for
    # a dense model, so equal is not the same as absent.
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Qwen3.6-35B-A3B"].active_parameters == 3e9
    assert by_name["Qwen3.6-27B"].active_parameters == 27e9


def test_the_coding_score_is_read_where_the_table_publishes_one(flight: str):
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Qwen3.6-27B"].coding_score == 77.2
    assert by_name["Qwen3.6-35B-A3B"].coding_score == 73.4


def test_a_model_the_table_scores_at_nothing_carries_no_score(flight: str):
    # Five open-weight rows publish no coding score. Ranking drops them; the
    # parse states what the table states.
    by_name = {listing.name: listing for listing in parse(flight).listings}

    assert by_name["Kimi K3"].coding_score is None


def test_a_score_the_table_writes_as_something_other_than_a_number_is_not_one():
    # The twenty benchmark keys are the page's own schema and it is already
    # mid-migration, with two generations of one key side by side. A key that
    # starts holding a string drops the row from the ranking, rather than
    # failing arithmetic three modules away.
    table = parse(
        '"config":{"models":[{"name":"A-7B","parameters":"7B",'
        '"benchmarks":{"swe_bench_verified":"73.4"}}]}'
    )

    assert table.listings[0].coding_score is None


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
