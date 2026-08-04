import subprocess

import pytest

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio import unload


def test_unloading_asks_the_runtime_to_let_go(monkeypatch):
    asked = {}

    def run(argv, **kwargs):
        asked["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    unload("a/model-7b")

    assert asked["argv"][1:] == ["unload", "a/model-7b"]


def test_a_runtime_without_its_tool_says_which_tool(monkeypatch):
    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeUnreachableError, match="lms"):
        unload("a/model-7b")


def test_a_refused_unload_reports_what_the_tool_said(monkeypatch):
    def refuse(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "no such model")

    monkeypatch.setattr(subprocess, "run", refuse)
    with pytest.raises(RuntimeUnreachableError, match="no such model"):
        unload("a/model-7b")
