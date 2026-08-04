import httpx
import pytest

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio import catalogue, parse_models

HOST = "127.0.0.1:1234"


def serving(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_a_catalogue_comes_back_decoded(monkeypatch: pytest.MonkeyPatch):
    body = {"data": [{"id": "a/model-7b", "type": "llm", "state": "loaded"}]}
    _serve(monkeypatch, lambda request: httpx.Response(200, json=body))
    assert catalogue(HOST) == body


def test_nothing_listening_says_to_start_the_server(monkeypatch: pytest.MonkeyPatch):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _serve(monkeypatch, refuse)
    with pytest.raises(RuntimeUnreachableError, match="Start LM Studio") as raised:
        catalogue(HOST)
    assert HOST in str(raised.value)


def test_a_timeout_is_not_reported_as_a_dead_server(monkeypatch: pytest.MonkeyPatch):
    # A server loading a 35GB model is slow, not absent, and telling someone to
    # start what is already running sends them looking in the wrong place.
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    _serve(monkeypatch, stall)
    with pytest.raises(RuntimeUnreachableError, match="did not answer within"):
        catalogue(HOST)


def test_an_error_status_says_the_server_answered(monkeypatch: pytest.MonkeyPatch):
    _serve(monkeypatch, lambda request: httpx.Response(500))
    with pytest.raises(RuntimeUnreachableError, match="500") as raised:
        catalogue(HOST)
    assert "Start LM Studio" not in str(raised.value)


def test_a_page_that_is_not_json_names_what_came_back(monkeypatch: pytest.MonkeyPatch):
    # Pointing at the wrong port is the likeliest mistake, and it used to
    # surface as a decode error naming nothing the user typed.
    _serve(monkeypatch, lambda request: httpx.Response(200, html="<h1>hello</h1>"))
    with pytest.raises(RuntimeUnreachableError, match="not JSON") as raised:
        catalogue(HOST)
    assert HOST in str(raised.value)


def test_a_body_without_a_catalogue_is_not_an_empty_catalogue():
    with pytest.raises(RuntimeUnreachableError, match="catalogue"):
        parse_models({"error": {"message": "model loading failed"}})


def test_an_entry_without_an_identifier_is_named_as_such():
    with pytest.raises(RuntimeUnreachableError, match="no id"):
        parse_models({"data": [{"type": "llm", "state": "loaded"}]})


def _serve(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Point httpx.get at a transport that answers however the test wants."""
    transport = serving(handler)

    def get(url: str, **kwargs: object) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url)

    monkeypatch.setattr(httpx, "get", get)
