"""What a connection to LM Studio does when asked to hold one model.

The server is stood in for rather than the module's own functions: the
orchestration and the parsing under it are the halves most likely to disagree,
and patching between them would test neither.

What any runtime owes is stated once, in `tests/test_runtime_conformance.py`.
What is here is LM Studio's own: that it reaches "hold only this one" by
letting go of each model in turn before it loads, what that costs and what it
says while paying it, and a release whose answer cannot be taken at its word.
"""

import logging
import subprocess
import sys

import httpx
import pytest

from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.shared.exceptions import (
    ModelNotHeldError,
    RuntimeUnreachableError,
)
from tests.doubles import (
    answer_as_lm_studio,
    answer_the_load,
    refuse_to_let_go,
    take_the_release_and_free_nothing,
)

HOST = "127.0.0.1:1234"


def test_what_a_swap_costs_is_said_before_it_is_paid(monkeypatch, caplog):
    answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

    assert any(
        "Letting go of a/held-7b" in record.getMessage()
        and "cached prefix" in record.getMessage()
        for record in caplog.records
    )


def test_the_wait_for_a_load_is_said_while_it_is_waited_for(monkeypatch, caplog):
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

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

    connect(LMStudioConfig(host=HOST)).ensure_only("a/wanted-7b")

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

    connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

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
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

    assert asked["loaded"] is None


def test_a_model_already_held_answers_even_where_another_will_not_go(monkeypatch):
    # No load is being asked for, so there is nothing to refuse: the reason a
    # cold model is refused here is the wait and the swap it would pay into a
    # full pool, and a warm one pays neither. What the stuck model costs is
    # said out loud instead, which is what a person can act on.
    answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8192, "a/stuck-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    model = connect(LMStudioConfig(host=HOST)).ensure_only("a/wanted-7b")

    assert model.identifier == "a/wanted-7b"
    assert [
        held.identifier for held in connect(LMStudioConfig(host=HOST)).read_held()
    ] == [
        "a/wanted-7b",
        "a/stuck-7b",
    ]


def test_what_a_model_that_will_not_go_costs_is_said_where_the_run_goes_on(
    monkeypatch, caplog
):
    answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8192, "a/stuck-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/wanted-7b")

    assert any(
        "still holding a/stuck-7b" in record.getMessage() for record in caplog.records
    )


def test_a_model_that_will_not_stay_held_is_reported(monkeypatch):
    # The runtime took the load and is holding nothing, which the catalogue
    # is the only way to find out.
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    answer_the_load(
        monkeypatch,
        lambda model: httpx.Response(200, json={"model": model, "content": []}),
    )

    with pytest.raises(ModelNotHeldError, match="accepted"):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")


def test_a_model_that_did_not_stay_held_is_let_go_of_before_the_error(monkeypatch):
    # The runtime may have taken the weights even though the catalogue does
    # not say so, and nobody downstream knows to let them go.
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    answer_the_load(
        monkeypatch,
        lambda model: httpx.Response(200, json={"model": model, "content": []}),
    )

    with pytest.raises(ModelNotHeldError):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_a_load_that_is_interrupted_lets_go_of_what_it_started(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    def interrupted(model: str) -> httpx.Response:
        raise KeyboardInterrupt

    answer_the_load(monkeypatch, interrupted)

    with pytest.raises(KeyboardInterrupt):
        connect(LMStudioConfig(host=HOST)).ensure_only("a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_a_runtime_that_will_not_let_go_is_said_rather_than_raised(monkeypatch, caplog):
    # A run that has already finished is not worth failing over, but memory
    # still held is worth saying out loud.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).let_go("a/held-7b")

    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_a_release_that_freed_nothing_is_not_taken_at_its_word(monkeypatch, caplog):
    # A release the runtime accepted is a release it accepted, not memory that
    # came back. The catalogue is what settles it, and the answer a caller
    # branches on has to reflect that.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})
    take_the_release_and_free_nothing(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        came_back = connect(LMStudioConfig(host=HOST)).let_go("a/held-7b")

    assert came_back is False
    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_progress_is_silent_for_a_caller_that_configured_nothing():
    # A library that prints without being asked is a library that cannot be
    # embedded. In this process pytest has already attached a handler, so
    # the claim is only testable somewhere that has not.
    finished = subprocess.run(
        [
            sys.executable,
            "-c",
            "from offgrid.runtimes.lmstudio import lmstudio; "
            "lmstudio.log.info('progress'); "
            "lmstudio.log.warning('memory that did not come back')",
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
