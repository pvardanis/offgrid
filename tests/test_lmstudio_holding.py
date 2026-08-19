"""What a connection to LM Studio does when asked to hold one model.

The server is stood in for rather than the module's own functions: the
orchestration and the parsing under it are the halves most likely to disagree,
and patching between them would test neither.

What any runtime owes is stated once, in the `tests/test_runtime_*.py` suites.
What is here is LM Studio's own: that it reaches "hold only this one" by
letting go of each model in turn before it loads, what that costs and what it
says while paying it, and a release whose answer cannot be taken at its word.
"""

import logging
import subprocess
import sys

import httpx
import pytest

from offgrid.domain.running.model import ModelRequest
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.shared.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from tests.lmstudio_endpoint import (
    answer_the_load,
    answer_the_release,
    refuse_to_let_go,
    take_the_release_and_free_nothing,
)
from tests.lmstudio_server import answer_as_lm_studio

HOST = "127.0.0.1:1234"


def test_what_a_swap_costs_is_said_before_it_is_paid(monkeypatch, caplog):
    answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )

    assert any(
        "Letting go of a/held-7b" in record.getMessage()
        and "cached prefix" in record.getMessage()
        for record in caplog.records
    )


def test_the_wait_for_a_load_is_said_while_it_is_waited_for(monkeypatch, caplog):
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )

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

    connect(LMStudioConfig(host=HOST)).ensure_only(
        ModelRequest(identifier="a/wanted-7b")
    )

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

    connect(LMStudioConfig(host=HOST)).ensure_only(
        ModelRequest(identifier="a/other-7b")
    )

    assert asked["order"] == [
        ("let_go", "a/held-7b"),
        ("let_go", "a/also-held-7b"),
        ("loaded", "a/other-7b"),
    ]


def test_a_request_naming_no_model_is_refused_at_the_port(monkeypatch):
    # `hold_model` answers which model is resident before it asks the runtime,
    # so nothing reaching here should have that question open. A caller
    # embedding offgrid can reach the port directly, and the adapter has
    # nothing to settle it with.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError, match="No model was named"):
        connect(LMStudioConfig(host=HOST)).ensure_only(ModelRequest())


def test_a_window_is_changed_by_letting_go_first_and_loading_after(monkeypatch):
    # A second load does not replace the first here: LM Studio serves both
    # copies, at both windows, and ids the second `:2`. So the only way to
    # change a window is to free the copy that is held before asking again.
    asked = answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8000})

    connect(LMStudioConfig(host=HOST)).ensure_only(
        ModelRequest(identifier="a/wanted-7b", context_window=16000)
    )

    assert asked["order"] == [
        ("let_go", "a/wanted-7b"),
        ("loaded", "a/wanted-7b"),
    ]
    assert asked["window"] == 16000


def test_a_window_that_will_not_be_freed_is_not_loaded_on_top_of(monkeypatch):
    # The copy at the old window is still holding its memory, and loading
    # again would leave the machine serving the model twice over. What is said
    # names both windows, because "still holding a/wanted-7b, so a/wanted-7b
    # is not being loaded" reads as a model blocking itself.
    asked = answer_as_lm_studio(
        monkeypatch, holding={"a/wanted-7b": 8000}, stuck={"a/wanted-7b"}
    )

    with pytest.raises(RuntimeUnreachableError) as refused:
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/wanted-7b", context_window=16000)
        )

    said = str(refused.value)
    assert "8000" in said
    assert "16000" in said
    assert asked["loaded"] is None


def test_a_window_change_refused_by_the_pool_keeps_the_model_that_was_held(
    monkeypatch,
):
    # The wanted model is serving, at the wrong window, beside one that will
    # not go. Letting the wanted one go and then refusing the load costs its
    # memory and its cached prefix for nothing: the run fails either way, and
    # what was answering is gone. So the pool is settled before it is touched.
    asked = answer_as_lm_studio(
        monkeypatch,
        holding={"a/wanted-7b": 8000, "a/stuck-7b": 8192},
        stuck={"a/stuck-7b"},
    )

    with pytest.raises(RuntimeUnreachableError, match="a/stuck-7b"):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/wanted-7b", context_window=16000)
        )

    assert "a/wanted-7b" not in asked["let_go"]
    assert asked["loaded"] is None


def test_a_swap_that_freed_nothing_does_not_load_on_top_of_it(monkeypatch):
    # The model that would not go is still holding its memory. Asking the
    # runtime for another one either fails the load or starts the machine
    # swapping, and the wait for both is paid before either is found out.
    asked = answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192}
    )
    refuse_to_let_go(monkeypatch, "it would not go")

    with pytest.raises(RuntimeUnreachableError, match="still holding"):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )

    assert asked["loaded"] is None


def test_a_model_already_held_answers_even_where_another_will_not_go(monkeypatch):
    # No load is being asked for, so there is nothing to refuse: the reason a
    # cold model is refused here is the wait and the swap it would pay into a
    # full pool, and a warm one pays neither. What the stuck model costs is
    # said out loud instead, which is what a person can act on.
    answer_as_lm_studio(monkeypatch, holding={"a/wanted-7b": 8192, "a/stuck-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    model = connect(LMStudioConfig(host=HOST)).ensure_only(
        ModelRequest(identifier="a/wanted-7b")
    )

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
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/wanted-7b")
        )

    assert any(
        "still holding a/stuck-7b" in record.getMessage() for record in caplog.records
    )


def test_a_model_that_will_not_stay_held_is_reported(monkeypatch):
    # The runtime took the load and is holding nothing, which the catalogue
    # is the only way to find out.
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    answer_the_load(
        monkeypatch,
        lambda model: httpx.Response(200, json={"instance_id": model}),
    )

    with pytest.raises(ModelNotHeldError, match="accepted"):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )


def test_a_model_that_did_not_stay_held_is_let_go_of_before_the_error(monkeypatch):
    # The runtime may have taken the weights even though the catalogue does
    # not say so, and nobody downstream knows to let them go.
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})
    answer_the_load(
        monkeypatch,
        lambda model: httpx.Response(200, json={"instance_id": model}),
    )

    with pytest.raises(ModelNotHeldError):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )

    assert "a/other-7b" in asked["let_go"]


def test_a_load_that_is_interrupted_lets_go_of_what_it_started(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": 8192})

    def interrupted(model: str) -> httpx.Response:
        raise KeyboardInterrupt

    answer_the_load(monkeypatch, interrupted)

    with pytest.raises(KeyboardInterrupt):
        connect(LMStudioConfig(host=HOST)).ensure_only(
            ModelRequest(identifier="a/other-7b")
        )

    assert "a/other-7b" in asked["let_go"]


def test_a_runtime_that_will_not_let_go_is_said_rather_than_raised(monkeypatch, caplog):
    # A run that has already finished is not worth failing over, but memory
    # still held is worth saying out loud.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b": 8192})
    refuse_to_let_go(monkeypatch, "it would not go")

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(LMStudioConfig(host=HOST)).let_go("a/held-7b")

    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_every_copy_of_a_model_held_twice_is_let_go_of(monkeypatch):
    # LM Studio serves a model twice over where it was loaded twice, and a
    # release names one copy. Freeing the first, reporting success and leaving
    # the second resident is memory gone for the rest of the session, on a
    # machine whose whole premise is one model at a time.
    asked = answer_as_lm_studio(
        monkeypatch, holding={"a/held-7b": 8192, "a/held-7b:2": 8192}
    )

    came_back = connect(LMStudioConfig(host=HOST)).let_go("a/held-7b")

    assert came_back is True
    assert asked["let_go"] == ["a/held-7b", "a/held-7b:2"]


def test_a_model_the_runtime_already_evicted_is_memory_that_came_back(monkeypatch):
    # LM Studio evicts against a ceiling of its own, so a run's release can
    # arrive after the model has already gone. The runtime answers 404 for an
    # instance it is not holding, and reporting memory that is back as memory
    # that is not sends someone looking for nothing.
    answer_as_lm_studio(monkeypatch, cold={"a/held-7b": 8192})

    assert connect(LMStudioConfig(host=HOST)).let_go("a/held-7b") is True


def test_a_copy_nobody_saw_held_is_not_reported_as_a_refusal(monkeypatch, caplog):
    # The bare name is asked after on the chance the catalogue is behind. Where
    # it was not, the 404 that answers is a non-event, and putting it beside a
    # real refusal explains memory that is stuck with the wrong reason.
    answer_as_lm_studio(monkeypatch, holding={"a/held-7b:2": 8192})
    answer_the_release(
        monkeypatch,
        lambda instance: (
            httpx.Response(500, json={"error": {"message": "it would not go"}})
            if instance == "a/held-7b:2"
            else httpx.Response(404, json={"error": {"message": "is not loaded"}})
        ),
    )

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        came_back = connect(LMStudioConfig(host=HOST)).let_go("a/held-7b")

    assert came_back is False
    (said,) = [record.getMessage() for record in caplog.records]
    assert "it would not go" in said
    assert "is not loaded" not in said


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
