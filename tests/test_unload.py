import json

import httpx
import pytest

from offgrid.runtimes.lmstudio.holding import unload_model
from offgrid.shared.exceptions import RuntimeUnreachableError
from tests.doubles import serve_post

HOST = "127.0.0.1:1234"


def test_letting_go_names_the_instance_the_runtime_is_holding(monkeypatch):
    asked: dict = {}

    def release(request: httpx.Request) -> httpx.Response:
        asked["url"] = str(request.url)
        asked["body"] = json.loads(request.content)

        return httpx.Response(200, json={"instance_id": "a/model-7b"})

    serve_post(monkeypatch, release)

    unload_model(HOST, "a/model-7b")

    assert asked["url"] == f"http://{HOST}/api/v1/models/unload"
    assert asked["body"] == {"instance_id": "a/model-7b"}


def test_a_release_the_runtime_refuses_says_what_it_said(monkeypatch):
    serve_post(
        monkeypatch,
        lambda request: httpx.Response(
            404,
            json={
                "error": {
                    "type": "model_not_found",
                    "message": "Model with instance identifier 'a/model-7b' is "
                    "not loaded.",
                }
            },
        ),
    )

    with pytest.raises(RuntimeUnreachableError, match="is not loaded"):
        unload_model(HOST, "a/model-7b")


def test_a_release_that_never_arrived_says_where_it_was_sent(monkeypatch):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_post(monkeypatch, refuse)

    with pytest.raises(RuntimeUnreachableError, match=f"http://{HOST}"):
        unload_model(HOST, "a/model-7b")
