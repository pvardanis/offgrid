import subprocess

import httpx
import pytest

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio.holding import unload
from tests.doubles import run_tool, serve_get

HOST = "127.0.0.1:1234"


def _holding(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    """Answer the catalogue with one model in the state the test wants."""
    body = {"data": [{"id": "a/model-7b", "type": "llm", "state": state}]}
    serve_get(monkeypatch, lambda request: httpx.Response(200, json=body))


def test_unloading_asks_the_runtime_to_let_go(monkeypatch):
    asked = run_tool(monkeypatch)
    _holding(monkeypatch, "not-loaded")

    unload(HOST, "a/model-7b")

    assert asked["argv"][1:] == ["unload", "a/model-7b"]
    assert asked["check"] is False
    assert asked["capture_output"] is True
    assert asked["text"] is True


def test_a_runtime_without_its_tool_says_which_tool(monkeypatch):
    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeUnreachableError, match="lms"):
        unload(HOST, "a/model-7b")


def test_a_refused_unload_reports_what_the_tool_said(monkeypatch):
    run_tool(monkeypatch, returncode=1, stderr="no such model")

    with pytest.raises(RuntimeUnreachableError, match="no such model"):
        unload(HOST, "a/model-7b")


def test_a_model_the_tool_did_not_free_is_not_called_freed(monkeypatch):
    # `lms unload` exits 0 for a name it does not know, printing "Model Not
    # Found" and freeing nothing. The catalogue is what settles it.
    run_tool(monkeypatch, returncode=0, stdout="Model Not Found")
    _holding(monkeypatch, "loaded")

    with pytest.raises(RuntimeUnreachableError, match="still holding"):
        unload(HOST, "a/model-7b")
