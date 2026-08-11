"""What a connection to LM Studio does when asked to hold one model.

The server answers over HTTP and lets go through its own tool, so both are
stood in for here rather than the module's own functions: the orchestration
and the parsing under it are the halves most likely to disagree, and patching
between them would test neither.
"""

import json
import logging
import subprocess
from collections.abc import Sequence

import httpx
import pytest

from offgrid.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from offgrid.runtimes.lmstudio import connect
from tests.doubles import serve_get, serve_post

HOST = "127.0.0.1:1234"
CEILING = 262144


def _entry(identifier: str, *, served: int, in_memory: bool) -> dict:
    """Describe one model the way LM Studio's catalogue does."""
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": CEILING,
    }
    if in_memory:
        entry["loaded_context_length"] = served

    return entry


def _server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    holding: dict[str, int] | None = None,
    cold: dict[str, int] | None = None,
) -> dict:
    """Stand in for LM Studio, answering as what it holds changes.

    Each mapping is a model against the context it is served at. A cold model
    states only its ceiling until something loads it, which is what makes the
    difference between the two numbers visible.

    :param monkeypatch: The test's patcher.
    :param holding: Models in memory, against the context each is served at.
    :param cold: Models it has and is not holding.

    :return: What it was asked to load and let go of, in order.
    """
    served = {**(holding or {}), **(cold or {})}
    in_memory = dict.fromkeys(holding or {}, True) | dict.fromkeys(cold or {}, False)
    asked: dict = {"loaded": None, "let_go": [], "order": []}

    def catalogue(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    _entry(name, served=served[name], in_memory=state)
                    for name, state in in_memory.items()
                ]
            },
        )

    def load(request: httpx.Request) -> httpx.Response:
        identifier = json.loads(request.content)["model"]
        in_memory[identifier] = True
        asked["loaded"] = identifier
        asked["order"].append(("loaded", identifier))

        return httpx.Response(200, json={"model": identifier, "content": []})

    def tool(argv: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
        in_memory[argv[2]] = False
        asked["let_go"].append(argv[2])
        asked["order"].append(("let_go", argv[2]))

        return subprocess.CompletedProcess(list(argv), 0, "", "")

    serve_get(monkeypatch, catalogue)
    serve_post(monkeypatch, load)
    monkeypatch.setattr(subprocess, "run", tool)

    return asked


def test_a_model_the_runtime_does_not_have_names_what_lists_them(monkeypatch):
    _server(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError, match="offgrid doctor") as refused:
        connect(HOST).ensure_only("a/absent-7b")

    assert HOST in str(refused.value)


def test_what_a_swap_costs_is_said_before_it_is_paid(monkeypatch, caplog):
    _server(monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192})

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).ensure_only("a/other-7b")

    assert any(
        "Letting go of a/held-7b" in record.getMessage()
        and "cached prefix" in record.getMessage()
        for record in caplog.records
    )


def test_the_wait_for_a_load_is_said_while_it_is_waited_for(monkeypatch, caplog):
    _server(monkeypatch, cold={"a/other-7b": 8192})

    with caplog.at_level(logging.INFO, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).ensure_only("a/other-7b")

    said = [record.getMessage() for record in caplog.records]
    assert any("Loading a/other-7b" in line for line in said)
    assert any("ready in" in line for line in said)


def test_a_model_already_held_is_not_let_go_of_and_loaded_again(monkeypatch):
    # `loaded` answers in catalogue order, so a wanted model that is held but
    # not first is one `continue` away from being evicted and reloaded — the
    # whole wait, for no change.
    asked = _server(monkeypatch, holding={"a/held-7b": 8192, "a/wanted-7b": 8192})

    connect(HOST).ensure_only("a/wanted-7b")

    assert asked["loaded"] is None
    assert asked["let_go"] == ["a/held-7b"]


def test_every_model_held_is_let_go_not_only_the_first(monkeypatch):
    # LM Studio holds several at once. One left behind is memory nothing on
    # the machine can use for the whole session.
    asked = _server(
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
    asked = _server(monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 1, "", "it would not go"
        ),
    )

    with pytest.raises(RuntimeUnreachableError, match="still holding"):
        connect(HOST).ensure_only("a/other-7b")

    assert asked["loaded"] is None


def test_a_model_that_will_not_stay_held_is_reported(monkeypatch):
    # The runtime took the load and is holding nothing, which the catalogue
    # is the only way to find out.
    _server(monkeypatch, cold={"a/other-7b": 8192})
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
    asked = _server(monkeypatch, cold={"a/other-7b": 8192})
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
    asked = _server(monkeypatch, cold={"a/other-7b": 8192})

    def interrupted(request: httpx.Request) -> httpx.Response:
        raise KeyboardInterrupt

    serve_post(monkeypatch, interrupted)

    with pytest.raises(KeyboardInterrupt):
        connect(HOST).ensure_only("a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_letting_go_says_whether_the_memory_came_back(monkeypatch):
    # A log record is for a person. A caller embedding offgrid needs an
    # answer it can branch on.
    _server(monkeypatch, holding={"a/held-7b": 8192})

    assert connect(HOST).let_go("a/held-7b") is True


def test_letting_go_says_when_the_memory_did_not_come_back(monkeypatch):
    _server(monkeypatch, holding={"a/held-7b": 8192})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 1, "", "it would not go"
        ),
    )

    assert connect(HOST).let_go("a/held-7b") is False


def test_a_runtime_that_will_not_let_go_is_said_rather_than_raised(monkeypatch, caplog):
    # A run that has already finished is not worth failing over, but memory
    # still held is worth saying out loud.
    _server(monkeypatch, holding={"a/held-7b": 8192})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 1, "", "it would not go"
        ),
    )

    with caplog.at_level(logging.WARNING, logger="offgrid.runtimes.lmstudio"):
        connect(HOST).let_go("a/held-7b")

    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_what_is_held_is_read_back_as_it_is_served(monkeypatch):
    _server(monkeypatch, holding={"a/held-7b": 8192}, cold={"a/other-7b": 8192})

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
    _server(monkeypatch, cold={"a/other-7b": 32768})

    model = connect(HOST).ensure_only("a/other-7b")

    assert model.identifier == "a/other-7b"
    assert model.context_limit == 32768
