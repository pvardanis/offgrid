"""What being a runtime means, asked of every adapter there is.

Each of these is defensible for a runtime that is not the one that happens to
be written: it states something the domain relies on, not something an adapter
happens to do. What one runtime does and another does not — the endpoints, the
tool, the payload — stays in that adapter's own file.

An adapter is done when this passes. `tests/runtimes_under_test.py` is where a
second one joins, and it is the only edit to the suite that adding one takes.
"""

import pytest

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.shared.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from tests.runtimes_under_test import RUNTIMES_UNDER_TEST, RuntimeUnderTest


@pytest.fixture(params=RUNTIMES_UNDER_TEST, ids=lambda under_test: under_test.name)
def runtime(request: pytest.FixtureRequest) -> RuntimeUnderTest:
    """The adapter this run of the suite is asking about.

    :param request: The running test.

    :return: One adapter, and what standing its runtime in takes.
    """
    return request.param


def test_a_model_is_answered_for_as_it_is_served_not_as_it_is_catalogued(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A catalogue entry states a ceiling. A model in memory states the window
    # it is actually served at. Sizing an agent's context from the ceiling
    # means it never compacts and the runtime truncates the prefix instead,
    # which is the failure compacting exists to avoid.
    runtime.arrange_serving(monkeypatch, cold={"a/wanted-7b": 32768}, catalogued=262144)

    model = runtime.connect().ensure_only("a/wanted-7b")

    assert model.identifier == "a/wanted-7b"
    assert (model.context_window, model.context_ceiling) == (32768, 262144)


def test_only_the_model_that_will_answer_is_held_afterwards(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # One machine, one pool of memory. What reaching that state costs is the
    # adapter's business; that it was reached is not.
    runtime.arrange_serving(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/wanted-7b": 8192}
    )
    connection = runtime.connect()

    connection.ensure_only("a/wanted-7b")

    assert [model.identifier for model in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_already_held_is_answered_for_and_stays_held(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Letting go of the wanted model to load it again is the whole wait for no
    # change, and it throws away the prefix already in memory.
    runtime.arrange_serving(monkeypatch, holding={"a/wanted-7b": 8192})
    connection = runtime.connect()

    model = connection.ensure_only("a/wanted-7b")

    assert model.identifier == "a/wanted-7b"
    assert [held.identifier for held in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_the_runtime_does_not_have_is_refused_by_name(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError) as refused:
        runtime.connect().ensure_only("a/absent-7b")

    said = str(refused.value)
    assert "a/absent-7b" in said
    assert runtime.address in said
    assert "offgrid doctor" in said


def test_a_model_the_runtime_took_and_does_not_hold_is_reported(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A runtime that accepted the load and is holding nothing has answered
    # every question but the one that matters, so reading back what is held is
    # the only way to find out. Which error arrives says which of the two
    # happened, and a caller branches on that.
    runtime.arrange_taking_without_holding(monkeypatch, model="a/wanted-7b")

    with pytest.raises(ModelNotHeldError) as reported:
        runtime.connect().ensure_only("a/wanted-7b")

    assert "a/wanted-7b" in str(reported.value)


def test_what_is_held_is_a_different_question_from_what_there_is(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Both are answerable, however many requests that costs the adapter.
    runtime.arrange_serving(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/cold-7b": 8192}
    )
    connection = runtime.connect()

    assert [model.identifier for model in connection.read_catalogue()] == [
        "a/held-7b",
        "a/cold-7b",
    ]
    assert [model.identifier for model in connection.read_held()] == ["a/held-7b"]


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


def test_a_runtime_that_cannot_be_reached_is_offgrids_error_naming_the_address(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A caller branches on which error arrives, so which one arrives is part of
    # the contract rather than the adapter's choice.
    runtime.arrange_unreachable(monkeypatch)
    connection = runtime.connect()

    for ask in (
        connection.read_catalogue,
        connection.read_held,
        lambda: connection.ensure_only("a/wanted-7b"),
    ):
        with pytest.raises(RuntimeUnreachableError) as unreached:
            ask()

        assert runtime.address in str(unreached.value)


def test_what_a_connection_settled_is_readable_without_reaching_the_runtime(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # The dialect and the capabilities are settled when the connection opens,
    # so reading them is free and cannot fail. `run` checks the dialect before
    # anything is loaded, which is only worth doing if it costs nothing.
    runtime.arrange_unreachable(monkeypatch)
    connection = runtime.connect()

    assert isinstance(connection.dialect, Dialect)
    assert isinstance(connection.capabilities, Capabilities)
