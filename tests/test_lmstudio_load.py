import json

import httpx
import pytest

from offgrid.runtimes.lmstudio.holding import LOAD_TIMEOUT_SECONDS
from offgrid.shared.exceptions import RuntimeUnreachableError
from tests.doubles import serve_post

HOST = "127.0.0.1:1234"


def test_a_load_is_waited_on_for_as_long_as_it_is_given(
    monkeypatch: pytest.MonkeyPatch,
):
    # Weights come off disk at gigabytes a second: the catalogue's few
    # seconds would give up on a load that is going fine.
    from offgrid.runtimes.lmstudio.holding import load_model

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["timeout"] = request.extensions["timeout"]["read"]
        return httpx.Response(200, json={"instance_id": "a/model-7b"})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b")

    assert asked["timeout"] == LOAD_TIMEOUT_SECONDS


def test_loading_a_model_names_it_to_the_endpoint_that_takes_weights(
    monkeypatch: pytest.MonkeyPatch,
):
    from offgrid.runtimes.lmstudio.holding import load_model

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["body"] = json.loads(request.content)
        return httpx.Response(200, json={"instance_id": "a/model-7b"})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b", timeout=5)

    assert asked["url"].endswith("/api/v1/models/load")
    assert asked["body"]["model"] == "a/model-7b"


def test_a_load_asked_for_a_window_says_so_in_the_request(
    monkeypatch: pytest.MonkeyPatch,
):
    # The window travels with the weights: it is settled as the model comes
    # into memory, and nothing afterwards changes what it is served at.
    from offgrid.runtimes.lmstudio.holding import load_model

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["body"] = json.loads(request.content)
        return httpx.Response(200, json={"instance_id": "a/model-7b"})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b", window=8000, timeout=5)

    assert asked["body"]["context_length"] == 8000


def test_a_load_asked_for_no_window_names_none(monkeypatch: pytest.MonkeyPatch):
    # Saying nothing is how a run inherits: the runtime serves whatever its
    # own configuration last remembered, and a number offgrid made up would
    # replace a person's choice with one nobody made.
    from offgrid.runtimes.lmstudio.holding import load_model

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["body"] = json.loads(request.content)
        return httpx.Response(200, json={"instance_id": "a/model-7b"})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b", timeout=5)

    assert "context_length" not in asked["body"]


def test_a_load_that_never_finishes_says_so(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio.holding import load_model

    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("still loading", request=request)

    serve_post(monkeypatch, stall)
    with pytest.raises(RuntimeUnreachableError, match="did not finish loading"):
        load_model(HOST, "a/model-7b", timeout=5)


def test_a_load_whose_answer_cannot_be_read_is_offgrids_error_too(
    monkeypatch: pytest.MonkeyPatch,
):
    from offgrid.runtimes.lmstudio.holding import load_model

    def mangled(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("bad gzip", request=request)

    serve_post(monkeypatch, mangled)

    with pytest.raises(RuntimeUnreachableError, match="could not be read"):
        load_model(HOST, "a/model-7b", timeout=5)


def test_a_refused_load_reports_what_the_server_said(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio.holding import load_model

    serve_post(monkeypatch, lambda request: httpx.Response(400, text="no such model"))
    with pytest.raises(RuntimeUnreachableError, match="400") as refused:
        load_model(HOST, "a/model-7b", timeout=5)

    assert "no such model" in str(refused.value)


def test_a_load_of_a_name_the_runtime_does_not_have_says_which_name(
    monkeypatch: pytest.MonkeyPatch,
):
    # Captured from the live server: the load endpoint answers 404 for a name
    # it does not have, where the messages endpoint answered 200 as whatever
    # happened to be loaded.
    from offgrid.runtimes.lmstudio.holding import load_model

    not_found = {
        "error": {
            "type": "model_not_found",
            "message": "Model totally/made-up-9000 not found in downloaded models",
        }
    }
    serve_post(monkeypatch, lambda request: httpx.Response(404, json=not_found))

    with pytest.raises(RuntimeUnreachableError, match="404") as refused:
        load_model(HOST, "totally/made-up-9000", timeout=5)

    assert "not found in downloaded models" in str(refused.value)
