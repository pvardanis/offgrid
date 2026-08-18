"""Asking a runtime what it has, asked of every adapter there is.

What there is and what is held are two questions, both answerable. What a
connection settled reads without reaching anything, which is what lets a
run refuse an impossible pairing before it pays for a load.
"""

import pytest

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.shared.exceptions import RuntimeUnreachableError
from tests.runtimes_under_test import RuntimeUnderTest


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
