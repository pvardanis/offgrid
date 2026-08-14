import httpx
import pytest

from offgrid.leaderboards.onyx import TIMEOUT_SECONDS, URL, fetch, parse
from offgrid.shared.exceptions import (
    LeaderboardUnreachableError,
    LeaderboardUnreadableError,
)
from tests.doubles import serve_get


def test_the_page_is_asked_for_as_flight_text_not_as_a_page(
    monkeypatch: pytest.MonkeyPatch,
):
    # Without the header the same route answers 190KB of HTML with the table
    # buried in script tags, which is a second parser to keep working.
    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["rsc"] = request.headers.get("RSC")
        asked["timeout"] = request.extensions["timeout"]["read"]
        return httpx.Response(200, text='"config":{"models":[]}')

    serve_get(monkeypatch, answer)
    fetch()

    assert asked["url"] == URL
    assert asked["rsc"] == "1"
    assert asked["timeout"] == TIMEOUT_SECONDS


def test_the_flight_text_comes_back_as_it_was_sent(monkeypatch: pytest.MonkeyPatch):
    serve_get(monkeypatch, lambda request: httpx.Response(200, text='0:{"a":1}'))

    assert fetch() == '0:{"a":1}'


def test_a_leaderboard_nothing_can_reach_says_so_and_says_it_is_the_network(
    monkeypatch: pytest.MonkeyPatch,
):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nodename nor servname provided")

    serve_get(monkeypatch, refuse)

    with pytest.raises(LeaderboardUnreachableError) as raised:
        fetch()

    assert URL in str(raised.value)
    assert "network" in str(raised.value)


def test_a_leaderboard_that_answers_an_error_is_not_read_as_a_table(
    monkeypatch: pytest.MonkeyPatch,
):
    serve_get(monkeypatch, lambda request: httpx.Response(503, text="unavailable"))

    with pytest.raises(LeaderboardUnreachableError) as raised:
        fetch()

    assert "503" in str(raised.value)


def test_a_page_the_table_has_moved_out_of_names_what_was_looked_for():
    # A redesign and a bug look identical from here, and the difference is
    # worth the maintainer's time rather than a shrug.
    with pytest.raises(LeaderboardUnreadableError) as raised:
        parse('0:["$","div",null,{"children":"nothing of the sort"}]')

    assert URL in str(raised.value)
    assert '"config":{' in str(raised.value)


def test_a_table_holding_no_models_is_a_failure_not_an_empty_shortlist():
    # An empty list would print as "nothing fits this machine", which is a
    # statement about the machine and would be a lie.
    with pytest.raises(LeaderboardUnreadableError) as raised:
        parse('{"config":{"lastUpdated":"2026-07-20","benchmarks":{}}}')

    assert "no list of models" in str(raised.value)


def test_a_table_that_is_not_json_where_it_should_be_says_so():
    with pytest.raises(LeaderboardUnreadableError) as raised:
        parse('"config":{"models": [oops}')

    assert URL in str(raised.value)


def test_a_test_that_reaches_the_leaderboard_by_omission_is_refused():
    # The guard in conftest.py, checked: without it this test depends on
    # someone else's site being up, and the whole suite quietly does too.
    with pytest.raises(AssertionError) as raised:
        fetch()

    assert "reached the network" in str(raised.value)


def test_a_leaderboard_that_takes_too_long_says_how_long_it_waited(
    monkeypatch: pytest.MonkeyPatch,
):
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    serve_get(monkeypatch, stall)

    with pytest.raises(LeaderboardUnreachableError) as raised:
        fetch()

    assert f"{TIMEOUT_SECONDS}s" in str(raised.value)


def test_a_size_written_in_a_way_that_is_not_a_number_is_not_a_size():
    # The table writes "N/A" today. Whatever it writes tomorrow, a row offgrid
    # cannot size is a row it leaves out rather than one it guesses at.
    table = parse(
        '"config":{"lastUpdated":"2026-07-20","models":'
        '[{"name":"A-Model","parameters":"severalB"},'
        '{"name":"A-Sized-Model","parameters":"7B"}]}'
    )

    assert [listing.name for listing in table.listings] == ["A-Sized-Model"]


def test_a_table_whose_rows_cannot_be_read_is_a_failure_not_an_empty_shortlist():
    # Rows that carry none of the keys they carried is what a schema change
    # looks like from here, and printing "nothing fits this machine" from it
    # would be a statement about the machine rather than about the table.
    with pytest.raises(LeaderboardUnreadableError) as raised:
        parse('"config":{"lastUpdated":"2026-07-20","models":[{"model":"A"},"B"]}')

    assert URL in str(raised.value)
    assert "2 models" in str(raised.value)


def test_a_table_that_has_moved_is_followed_rather_than_called_a_redesign(
    monkeypatch: pytest.MonkeyPatch,
):
    # A page that moved and a page that was rewritten are fixed differently,
    # and a redirect read as an empty body sends the maintainer to the wrong
    # one.
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/best-llm-for-coding":
            return httpx.Response(308, headers={"location": "/coding-leaderboard"})

        return httpx.Response(200, text='"config":{"models":[]}')

    serve_get(monkeypatch, answer)

    assert '"config":{' in fetch()


def test_a_row_whose_operational_block_is_null_is_not_a_traceback():
    # The research note warns that a parser must tolerate a missing key and
    # a null one, and they are not the same: a default only fires when the
    # key is absent.
    table = parse(
        '"config":{"models":[{"name":"A-7B","parameters":"7B","operational":null}]}'
    )

    assert table.listings[0].license is None


def test_a_row_with_no_name_is_still_printable():
    table = parse('"config":{"models":[{"name":null,"parameters":"7B"}]}')

    assert f"{table.listings[0].name:<24}".strip()


def test_a_table_that_lists_no_models_at_all_is_a_failure():
    # A page that rendered its table empty is a broken page, not a verdict
    # on this machine.
    with pytest.raises(LeaderboardUnreadableError) as raised:
        parse('"config":{"lastUpdated":"2026-07-20","models":[]}')

    assert URL in str(raised.value)


def test_a_redirect_that_never_settles_is_reported_as_the_network(
    monkeypatch: pytest.MonkeyPatch,
):
    # Following redirects is what makes this reachable: a captive portal or
    # a consent page that bounces forever is the case this command exists to
    # report as a sentence.
    def bounce(request: httpx.Request) -> httpx.Response:
        return httpx.Response(308, headers={"location": "/round-again"})

    serve_get(monkeypatch, bounce)

    with pytest.raises(LeaderboardUnreachableError) as raised:
        fetch()

    assert "network" in str(raised.value)
