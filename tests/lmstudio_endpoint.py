"""One of LM Studio's endpoints, answering differently from the rest of it.

A state a whole server cannot be put into by saying what it holds: a release
it refuses, a release it takes and acts on for nothing, a load whose answer is
its own. Each composes onto the server already standing in, so everything the
test did not arrange goes on being answered.
"""

import httpx
import pytest

from offgrid.runtimes.lmstudio.holding import LOAD, UNLOAD


def refuse_to_let_go(monkeypatch: pytest.MonkeyPatch, complaint: str) -> None:
    """Answer as a runtime that will not let go of anything it is holding.

    :param monkeypatch: The test's patcher.
    :param complaint: What the runtime says about it.
    """
    answer_the_release(
        monkeypatch,
        lambda instance: httpx.Response(500, json={"error": {"message": complaint}}),
    )


def take_the_release_and_free_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer as a runtime that accepts a release and goes on holding the model.

    :param monkeypatch: The test's patcher.
    """
    answer_the_release(
        monkeypatch,
        lambda instance: httpx.Response(200, json={"instance_id": instance}),
    )


def answer_the_release(monkeypatch: pytest.MonkeyPatch, answer) -> None:
    """Answer the release however a test wants, leaving the rest as it was.

    The catalogue is left saying what it said, which is how a release that
    freed nothing is arranged at all.

    :param monkeypatch: The test's patcher.
    :param answer: Called with the instance id, answering with a response.
    """
    _take_over(monkeypatch, UNLOAD, lambda body: answer(body["instance_id"]))


def answer_the_load(monkeypatch: pytest.MonkeyPatch, answer) -> None:
    """Answer the load however a test wants, leaving the rest as it was.

    :param monkeypatch: The test's patcher.
    :param answer: Called with the model, answering with a response.
    """
    _take_over(monkeypatch, LOAD, lambda body: answer(body["model"]))


def _take_over(monkeypatch: pytest.MonkeyPatch, path: str, answer) -> None:
    """Answer one endpoint, leaving whatever was arranged before it serving.

    A test that replaced `httpx.post` outright would answer the load and the
    release with the same handler, and lose whichever of the two it was not
    arranging.

    So this composes onto what is already standing in, and a server has to be
    standing in first. Refused rather than allowed, because arranging one
    endpoint against the real `httpx.post` reaches the network guard on the
    call this takes over and nowhere else — a double that answers one request
    and abandons the rest is a test that proves less than it reads as.

    :param monkeypatch: The test's patcher.
    :param path: The endpoint to take over.
    :param answer: Called with the decoded body, answering with a response.

    :raise AssertionError: When no server has been stood in yet.
    """
    serving = httpx.post

    if getattr(serving, "__module__", "httpx").startswith("httpx"):
        raise AssertionError(
            f"Nothing is standing in for the server, so taking over {path} "
            "would leave every other call reaching for one. Call "
            "answer_as_lm_studio first."
        )

    def post(url: str, json: dict, timeout: float = 0) -> httpx.Response:
        if url.endswith(path):
            return answer(json)

        return serving(url, json=json, timeout=timeout)

    monkeypatch.setattr(httpx, "post", post)
