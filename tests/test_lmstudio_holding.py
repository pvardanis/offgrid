"""What a connection to LM Studio does when asked to hold one model.

The server answers over HTTP and lets go through its own tool, so both are
stood in for rather than the module's own functions: the orchestration and the
parsing under it are the halves most likely to disagree, and patching between
them would test neither.
"""

import logging
import subprocess
import sys

import httpx
import pytest

from offgrid.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from offgrid.runtimes.lmstudio import connect
from tests.doubles import answer_as_lm_studio, refuse_to_let_go, serve_post

HOST = "127.0.0.1:1234"


def test_a_model_the_runtime_does_not_have_names_what_lists_them(monkeypatch):
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError, match="offgrid doctor") as refused:
        connect(HOST).ensure_only("a/absent-7b")

    assert HOST in str(refused.value)


def test_what_a_swap_costs_is_said_before_it_is_paid(monkeypatch, caplog):
    answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).ensure_only("a/other-7b")

    assert any(
        "Letting go of a/held-7b" in record.getMessage()
        and "cached prefix" in record.getMessage()
        for record in caplog.records
    )


def test_the_wait_for_a_load_is_said_while_it_is_waited_for(monkeypatch, caplog):
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).ensure_only("a/other-7b")

    said = [record.getMessage() for record in caplog.records]
    assert any("Loading a/other-7b" in line for line in said)
    assert any("ready in" in line for line in said)


def test_a_model_already_held_is_not_let_go_of_and_loaded_again(monkeypatch):
    # `loaded` answers in catalogue order, so a wanted model that is held but
    # not first is one `continue` away from being evicted and reloaded — the
    # whole wait, for no change.
    asked = answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192, "a/wanted-7b": 8192}
    )

    connect(HOST).ensure_only("a/wanted-7b")

    assert asked["loaded"] is None
    assert asked["let_go"] == ["a/held-7b"]


def test_every_model_held_is_let_go_not_only_the_first(monkeypatch):
    # LM Studio holds several at once. One left behind is memory nothing on
    # the machine can use for the whole session.
    asked = answer_as_lm_studio(
        monkeypatch,
        holding={"a/held-7b": 8192, "a/also-held-7b": 8192},
        cold={"a/other-7b": 8192},
    )

    connect(HOST).ensure_only("a/other-7b")

    assert asked["order"] == [
        ("let_go", "a/held-7b"),
        ("let_go", "a/also-held-7b"),
        ("loaded", "a/other-7b"),
    ]


def test_a_swap_that_freed_nothing_does_not_load_on_top_of_it(monkeypatch):
    # The model that would not go is still holding its memory. Asking the
    # runtime for another one either fails the load or starts the machine
    # swapping, and the wait for both is paid before either is found out.
    asked = answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )
    refuse_to_let_go(monkeypatch, "it would not go")

    with pytest.raises(RuntimeUnreachableError, match="still holding"):
        connect(HOST).ensure_only("a/other-7b")

    assert asked["loaded"] is None


def test_a_model_already_held_answers_even_where_another_will_not_go(monkeypatch):
    # No load is being asked for, so there is nothing to refuse: the reason a
    # cold model is refused here is the wait and the swap it would pay into a
    # full pool, and a warm one pays neither. What the stuck model costs is
    # said out loud instead, which is what a person can act on.
    answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8192, "a/stuck-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    model = connect(HOST).ensure_only("a/wanted-7b")

    assert model.identifier == "a/wanted-7b"
    assert [held.identifier for held in connect(HOST).read_held()] == [
        "a/wanted-7b",
        "a/stuck-7b",
    ]


def test_what_a_model_that_will_not_go_costs_is_said_where_the_run_goes_on(
    monkeypatch, caplog
):
    answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8192, "a/stuck-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).ensure_only("a/wanted-7b")

    assert any(
        "still holding a/stuck-7b" in record.getMessage() for record in caplog.records
    )


def test_a_model_that_will_not_stay_held_is_reported(monkeypatch):
    # The runtime took the load and is holding nothing, which the catalogue
    # is the only way to find out.
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    serve_post(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"model": "a/other-7b", "content": []}
        ),
    )

    with pytest.raises(ModelNotHeldError, match="accepted"):
        connect(HOST).ensure_only("a/other-7b")


def test_a_model_that_did_not_stay_held_is_let_go_of_before_the_error(monkeypatch):
    # The runtime may have taken the weights even though the catalogue does
    # not say so, and nobody downstream knows to let them go.
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    serve_post(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"model": "a/other-7b", "content": []}
        ),
    )

    with pytest.raises(ModelNotHeldError):
        connect(HOST).ensure_only("a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_a_load_that_is_interrupted_lets_go_of_what_it_started(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    def interrupted(request: httpx.Request) -> httpx.Response:
        raise KeyboardInterrupt

    serve_post(monkeypatch, interrupted)

    with pytest.raises(KeyboardInterrupt):
        connect(HOST).ensure_only("a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_letting_go_says_whether_the_memory_came_back(monkeypatch):
    # A log record is for a person. A caller embedding offgrid needs an
    # answer it can branch on.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})

    assert connect(HOST).let_go("a/held-7b") is True


def test_letting_go_says_when_the_memory_did_not_come_back(monkeypatch):
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    assert connect(HOST).let_go("a/held-7b") is False


def test_a_runtime_that_will_not_let_go_is_said_rather_than_raised(monkeypatch, caplog):
    # A run that has already finished is not worth failing over, but memory
    # still held is worth saying out loud.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).let_go("a/held-7b")

    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_what_is_held_is_read_back_as_it_is_served(monkeypatch):
    answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )

    connection = connect(HOST)

    assert [model.identifier for model in connection.read_held()] == ["a/held-7b"]
    assert [model.identifier for model in connection.read_catalogue()] == [
        "a/held-7b",
        "a/other-7b",
    ]


def test_a_model_is_answered_for_as_it_is_served_not_as_it_is_catalogued(monkeypatch):
    # A catalogue entry states a model's ceiling until it is loaded, and the
    # window it is served at once it is. Sizing an agent's context from the
    # ceiling means never compacting, and the runtime truncates the prefix
    # instead — which is the failure compacting exists to avoid.
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 32768})

    model = connect(HOST).ensure_only("a/other-7b")

    assert model.identifier == "a/other-7b"
    assert model.context_limit == 32768


def test_progress_is_silent_for_a_caller_that_configured_nothing():
    # A library that prints without being asked is a library that cannot be
    # embedded. In this process pytest has already attached a handler, so
    # the claim is only testable somewhere that has not.
    finished = subprocess.run(
        [
            sys.executable,
            "-c",
            "from offgrid.runtimes.lmstudio import connection; "
            "connection.log.info('progress'); "
            "connection.log.warning('memory that did not come back')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.stdout == ""
    assert "progress" not in finished.stderr
    # A warning is different: memory still held is worth surfacing even to a
    # caller that asked for nothing, and Python's last resort handler shows it.
    assert "memory that did not come back" in finished.stderr
