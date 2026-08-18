import json

import httpx
import pytest

from offgrid.runtimes.lmstudio.catalogue import (
    TIMEOUT_SECONDS,
    get_catalogue_payload,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.holding import LOAD_TIMEOUT_SECONDS
from offgrid.shared.exceptions import RuntimeUnreachableError
from tests.doubles import serve_get, serve_post

HOST = "127.0.0.1:1234"


def test_a_catalogue_comes_back_decoded(monkeypatch: pytest.MonkeyPatch):
    body = {"data": [{"id": "a/model-7b", "type": "llm", "state": "loaded"}]}
    serve_get(monkeypatch, lambda request: httpx.Response(200, json=body))
    assert get_catalogue_payload(HOST) == body


def test_the_catalogue_is_asked_for_at_the_address_given(
    monkeypatch: pytest.MonkeyPatch,
):
    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["timeout"] = request.extensions["timeout"]["read"]
        return httpx.Response(200, json={"data": []})

    serve_get(monkeypatch, answer)
    get_catalogue_payload(HOST)

    assert asked["url"] == f"http://{HOST}/api/v0/models"
    assert asked["timeout"] == TIMEOUT_SECONDS


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


def test_nothing_listening_says_to_start_the_server(monkeypatch: pytest.MonkeyPatch):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)
    with pytest.raises(RuntimeUnreachableError, match="Start LM Studio") as raised:
        get_catalogue_payload(HOST)
    assert HOST in str(raised.value)


def test_a_timeout_is_not_reported_as_a_dead_server(monkeypatch: pytest.MonkeyPatch):
    # A server loading a 35GB model is slow, not absent, and telling someone to
    # start what is already running sends them looking in the wrong place.
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    serve_get(monkeypatch, stall)
    with pytest.raises(RuntimeUnreachableError, match="did not answer within"):
        get_catalogue_payload(HOST)


def test_an_error_status_says_the_server_answered(monkeypatch: pytest.MonkeyPatch):
    serve_get(monkeypatch, lambda request: httpx.Response(500))
    with pytest.raises(RuntimeUnreachableError, match="500") as raised:
        get_catalogue_payload(HOST)
    assert "Start LM Studio" not in str(raised.value)


def test_a_page_that_is_not_json_names_what_came_back(monkeypatch: pytest.MonkeyPatch):
    # Pointing at the wrong port is the likeliest mistake, and it used to
    # surface as a decode error naming nothing the user typed.
    serve_get(monkeypatch, lambda request: httpx.Response(200, html="<h1>hello</h1>"))
    with pytest.raises(RuntimeUnreachableError, match="not JSON") as raised:
        get_catalogue_payload(HOST)
    assert HOST in str(raised.value)


def test_an_answer_that_cannot_be_read_is_offgrids_error_not_httpxs(
    monkeypatch: pytest.MonkeyPatch,
):
    # A body announcing an encoding it is not in raises `DecodingError`,
    # which is not a `TransportError` and so travelled as itself. It reaches
    # `let_go` in a `finally`, where anything raised replaces what the run
    # was about to report.
    def mangled(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("bad gzip", request=request)

    serve_get(monkeypatch, mangled)

    with pytest.raises(RuntimeUnreachableError, match="could not be read") as raised:
        get_catalogue_payload(HOST)

    assert HOST in str(raised.value)


def test_an_entry_without_an_identifier_is_named_as_such_when_reading_what_is_held():
    # `loaded` reads ids before `parse_models` gets to check them, so an
    # entry with no id at all arrived as a `KeyError` from inside offgrid.
    with pytest.raises(RuntimeUnreachableError, match="no id"):
        get_loaded_models({"data": [{"type": "llm", "state": "loaded"}]})


def test_a_body_without_a_catalogue_is_not_an_empty_catalogue():
    with pytest.raises(RuntimeUnreachableError, match="catalogue"):
        parse_models_from_payload({"error": {"message": "model loading failed"}})


def test_an_entry_without_an_identifier_is_named_as_such():
    with pytest.raises(RuntimeUnreachableError, match="no id"):
        parse_models_from_payload({"data": [{"type": "llm", "state": "loaded"}]})


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
