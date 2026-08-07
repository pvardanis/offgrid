"""Stand-ins for the things offgrid talks to: a server, and a runtime's tool."""

import subprocess

import httpx
import pytest


def serve_get(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Point httpx.get at a transport that answers however the test wants.

    :param monkeypatch: The test's patcher.
    :param handler: Called with the request, answering with a response.
    """
    transport = httpx.MockTransport(handler)

    def get(
        url: str, headers: dict | None = None, timeout: float = 0
    ) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, headers=headers, timeout=timeout)

    monkeypatch.setattr(httpx, "get", get)


def serve_post(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Point httpx.post at a transport that answers however the test wants.

    :param monkeypatch: The test's patcher.
    :param handler: Called with the request, answering with a response.
    """
    transport = httpx.MockTransport(handler)

    def post(url: str, json: dict, timeout: float = 0) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.post(url, json=json, timeout=timeout)

    monkeypatch.setattr(httpx, "post", post)


def run_tool(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> dict:
    """Answer for the runtime's command line tool, without running it.

    :param monkeypatch: The test's patcher.
    :param returncode: What the tool exits with.
    :param stdout: What it prints.
    :param stderr: What it complains with.

    :return: How it was called.
    """
    asked: dict = {}

    def run(argv, **kwargs):
        asked["argv"] = list(argv)
        asked.update(kwargs)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", run)

    return asked
