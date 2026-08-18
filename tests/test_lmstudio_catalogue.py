import httpx
import pytest

from offgrid.runtimes.lmstudio.catalogue import (
    TIMEOUT_SECONDS,
    get_catalogue_payload,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.shared.exceptions import RuntimeUnreachableError
from tests.doubles import serve_get

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
