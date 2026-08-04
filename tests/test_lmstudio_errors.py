import json

import httpx
import pytest

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio import catalogue, parse_models
from tests.doubles import serve_get, serve_post

HOST = "127.0.0.1:1234"


def test_a_catalogue_comes_back_decoded(monkeypatch: pytest.MonkeyPatch):
    body = {"data": [{"id": "a/model-7b", "type": "llm", "state": "loaded"}]}
    serve_get(monkeypatch, lambda request: httpx.Response(200, json=body))
    assert catalogue(HOST) == body


def test_nothing_listening_says_to_start_the_server(monkeypatch: pytest.MonkeyPatch):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)
    with pytest.raises(RuntimeUnreachableError, match="Start LM Studio") as raised:
        catalogue(HOST)
    assert HOST in str(raised.value)


def test_a_timeout_is_not_reported_as_a_dead_server(monkeypatch: pytest.MonkeyPatch):
    # A server loading a 35GB model is slow, not absent, and telling someone to
    # start what is already running sends them looking in the wrong place.
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    serve_get(monkeypatch, stall)
    with pytest.raises(RuntimeUnreachableError, match="did not answer within"):
        catalogue(HOST)


def test_an_error_status_says_the_server_answered(monkeypatch: pytest.MonkeyPatch):
    serve_get(monkeypatch, lambda request: httpx.Response(500))
    with pytest.raises(RuntimeUnreachableError, match="500") as raised:
        catalogue(HOST)
    assert "Start LM Studio" not in str(raised.value)


def test_a_page_that_is_not_json_names_what_came_back(monkeypatch: pytest.MonkeyPatch):
    # Pointing at the wrong port is the likeliest mistake, and it used to
    # surface as a decode error naming nothing the user typed.
    serve_get(monkeypatch, lambda request: httpx.Response(200, html="<h1>hello</h1>"))
    with pytest.raises(RuntimeUnreachableError, match="not JSON") as raised:
        catalogue(HOST)
    assert HOST in str(raised.value)


def test_a_body_without_a_catalogue_is_not_an_empty_catalogue():
    with pytest.raises(RuntimeUnreachableError, match="catalogue"):
        parse_models({"error": {"message": "model loading failed"}})


def test_an_entry_without_an_identifier_is_named_as_such():
    with pytest.raises(RuntimeUnreachableError, match="no id"):
        parse_models({"data": [{"type": "llm", "state": "loaded"}]})


def test_loading_a_model_asks_it_for_one_token(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio import load

    asked = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": []})

    serve_post(monkeypatch, answer)
    load(HOST, "a/model-7b", timeout=5)

    assert asked["url"].endswith("/v1/messages")
    assert asked["body"]["model"] == "a/model-7b"
    assert asked["body"]["max_tokens"] == 1


def test_a_load_that_never_finishes_says_so(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio import load

    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("still loading", request=request)

    serve_post(monkeypatch, stall)
    with pytest.raises(RuntimeUnreachableError, match="did not finish loading"):
        load(HOST, "a/model-7b", timeout=5)


def test_a_refused_load_reports_what_the_server_said(monkeypatch: pytest.MonkeyPatch):
    from offgrid.runtimes.lmstudio import load

    serve_post(monkeypatch, lambda request: httpx.Response(400, text="no such model"))
    with pytest.raises(RuntimeUnreachableError, match="400"):
        load(HOST, "a/model-7b", timeout=5)
