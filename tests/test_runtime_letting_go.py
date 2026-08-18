"""Letting one model go, asked of every runtime adapter there is.

What `let_go` promises: an answer rather than a raise, whichever way it
went, because both of its callers are cleanup — a `finally` at the end of
a run, and the release after a load that failed.
"""

import pytest

from tests.runtimes_under_test import RuntimeUnderTest


def test_what_is_held_reflects_a_release_rather_than_what_was_asked_for(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # What the runtime says it holds is the answer, not what offgrid believes
    # it did.
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})
    connection = runtime.connect()

    connection.let_go("a/held-7b")

    assert connection.read_held() == []


def test_letting_go_says_the_memory_came_back(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A log record is for a person. A caller embedding offgrid needs an answer
    # it can branch on.
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})

    assert runtime.connect().let_go("a/held-7b") is True


def test_letting_go_says_when_the_memory_did_not_come_back(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})
    runtime.arrange_stuck(monkeypatch)

    assert runtime.connect().let_go("a/held-7b") is False


def test_letting_go_answers_rather_than_raises_where_nothing_can_be_reached(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Both callers are cleanup — the `finally` at the end of a run, and the
    # release after a load that failed — so anything raised here replaces the
    # outcome the caller was about to report with the failure of tidying up
    # after it. A release that cannot be confirmed is a release that did not
    # happen, which is the answer that sends someone to look.
    runtime.arrange_unreachable(monkeypatch)

    assert runtime.connect().let_go("a/held-7b") is False
