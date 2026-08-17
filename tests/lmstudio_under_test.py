"""LM Studio, stood in for well enough to ask it what a runtime must do.

Its catalogue and its loads come over HTTP and it lets go through its own tool,
so all three are answered for. Every payload is shaped as the capture in
`tests/fixtures/lmstudio_models.json` shapes it — a live server's answer, never
a transcription of the documentation, which describes a version the app has
moved past.
"""

import subprocess
from dataclasses import dataclass

import httpx
import pytest

from offgrid.domain.running.runtime import Runtime
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from tests.doubles import (
    CEILING,
    answer_as_lm_studio,
    refuse_to_let_go,
    serve_get,
    serve_post,
)

HOST = "127.0.0.1:1234"


@dataclass(frozen=True)
class LMStudioUnderTest:
    """A copy of LM Studio the suite can put into whatever state it asks about."""

    @property
    def name(self) -> str:
        """What to call this adapter where a test says which one failed.

        :return: The runtime's name, as a profile spells it.
        """
        return "lmstudio"

    @property
    def address(self) -> str:
        """Where the stood-in runtime listens.

        :return: The address a person would have typed.
        """
        return HOST

    def connect(self) -> Runtime:
        """Open a connection to the runtime that was stood in.

        :return: The adapter under test, bound to `address`.
        """
        return connect(LMStudioConfig(host=HOST))

    def arrange_serving(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        holding: dict[str, int] | None = None,
        cold: dict[str, int] | None = None,
        catalogued: int = CEILING,
    ) -> None:
        """Answer as a runtime with these models, holding these of them.

        :param monkeypatch: The test's patcher.
        :param holding: Models in memory, against the context each is served
            at.
        :param cold: Models it has and is not holding, against the context each
            would be served at.
        :param catalogued: What every model states before it is loaded.
        """
        answer_as_lm_studio(monkeypatch, holding=holding, cold=cold, ceiling=catalogued)

    def arrange_stuck(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Answer as a runtime whose tool frees nothing it is asked to free.

        :param monkeypatch: The test's patcher.
        """
        refuse_to_let_go(monkeypatch, "it would not go")

    def arrange_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Answer as a runtime whose server nothing is listening for.

        The tool still exits cleanly, because it talks to the copy on this
        machine rather than to the server that stopped answering. That is the
        state a release has to survive: what it said is not what settles
        whether the memory came back.

        :param monkeypatch: The test's patcher.
        """

        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        serve_get(monkeypatch, refuse)
        serve_post(monkeypatch, refuse)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda argv, **kwargs: subprocess.CompletedProcess(list(argv), 0, "", ""),
        )
