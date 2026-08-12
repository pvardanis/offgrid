import subprocess

import pytest

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio.holding import unload
from tests.doubles import run_tool


def test_unloading_asks_the_runtime_to_let_go(monkeypatch):
    asked = run_tool(monkeypatch)

    unload("a/model-7b")

    assert asked["argv"][1:] == ["unload", "a/model-7b"]
    assert asked["check"] is False
    assert asked["capture_output"] is True
    assert asked["text"] is True


def test_a_runtime_without_its_tool_says_which_tool(monkeypatch):
    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeUnreachableError, match="lms"):
        unload("a/model-7b")


def test_a_refused_unload_reports_what_the_tool_said(monkeypatch):
    run_tool(monkeypatch, returncode=1, stderr="no such model")

    with pytest.raises(RuntimeUnreachableError, match="no such model"):
        unload("a/model-7b")


def test_what_the_tool_said_comes_back_for_whoever_checks(monkeypatch):
    # `lms unload` exits 0 for a name it does not know, printing "Model Not
    # Found" and freeing nothing. Its exit code cannot say so; what it printed
    # is what the caller has to go on, alongside the catalogue.
    run_tool(monkeypatch, returncode=0, stdout="Model Not Found\n")

    assert unload("a/model-7b") == "Model Not Found"
