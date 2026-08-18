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
        return httpx.Response(200, json={"model": "a/model-7b", "content": []})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b")

    assert asked["timeout"] == LOAD_TIMEOUT_SECONDS


def test_loading_a_model_asks_it_for_one_token(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio.holding import load_model

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": []})

    serve_post(monkeypatch, answer)
    load_model(HOST, "a/model-7b", timeout=5)

    assert asked["url"].endswith("/v1/messages")
    assert asked["body"]["model"] == "a/model-7b"
    assert asked["body"]["max_tokens"] == 1


def test_a_load_another_model_answers_is_refused(monkeypatch: pytest.MonkeyPatch):
    # Captured from the live server: asked for a name it does not have while
    # google/gemma-4-e4b was loaded, it answered 200 as gemma.
    from offgrid.runtimes.lmstudio.holding import load_model

    answered_as = {
        "id": "msg_7awwpgbekenxou8epgv27q",
        "type": "message",
        "role": "assistant",
        "content": [],
        "model": "google/gemma-4-e4b",
        "stop_reason": "max_tokens",
    }
    serve_post(monkeypatch, lambda request: httpx.Response(200, json=answered_as))

    with pytest.raises(RuntimeUnreachableError, match="google/gemma-4-e4b") as raised:
        load_model(HOST, "totally/made-up-model-9000", timeout=5)

    assert "totally/made-up-model-9000" in str(raised.value)


def test_a_load_the_right_model_answers_is_accepted(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio.holding import load_model

    served = {"content": [], "model": "a/model-7b"}
    serve_post(monkeypatch, lambda request: httpx.Response(200, json=served))

    load_model(HOST, "a/model-7b", timeout=5)


def test_a_load_answered_with_something_other_than_json_says_so(
    monkeypatch: pytest.MonkeyPatch,
):
    from offgrid.runtimes.lmstudio.holding import load_model

    serve_post(monkeypatch, lambda request: httpx.Response(200, html="<h1>hello</h1>"))

    with pytest.raises(RuntimeUnreachableError, match="not JSON"):
        load_model(HOST, "a/model-7b", timeout=5)


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
    with pytest.raises(RuntimeUnreachableError, match="400"):
        load_model(HOST, "a/model-7b", timeout=5)
