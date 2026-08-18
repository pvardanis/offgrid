"""LM Studio, stood in for well enough to ask it what a runtime must do.

Its catalogue, its loads and its releases all come over HTTP, so all three are
answered for. Every payload is shaped as the capture in
`tests/fixtures/lmstudio_models.json` shapes it — a live server's answer, never
a transcription of the documentation, which describes a version the app has
moved past.
"""

from dataclasses import dataclass

import httpx
import pytest

from offgrid.domain.running.runtime import Runtime
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from tests.doubles import CEILING, serve_get, serve_post
from tests.lmstudio_endpoint import answer_the_load, refuse_to_let_go
from tests.lmstudio_server import answer_as_lm_studio

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
        """Answer as a runtime that frees nothing it is asked to free.

        :param monkeypatch: The test's patcher.
        """
        refuse_to_let_go(monkeypatch, "it would not go")

    def arrange_taking_without_holding(
        self, monkeypatch: pytest.MonkeyPatch, *, model: str
    ) -> None:
        """Answer as a runtime that accepts a load and holds nothing.

        The load is answered as LM Studio answers a load it took, while the
        catalogue goes on saying the model is cold. The catalogue is the only
        way to find that out, which is the whole reason it is read back.

        :param monkeypatch: The test's patcher.
        :param model: The model it takes and does not hold.
        """
        answer_as_lm_studio(monkeypatch, cold={model: 8192})
        answer_the_load(
            monkeypatch,
            lambda served: httpx.Response(200, json={"model": served, "content": []}),
        )

    def arrange_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Answer as a runtime whose server nothing is listening for.

        Every call goes to it, the release included, so a release against it is
        one that cannot be confirmed rather than one that failed.

        :param monkeypatch: The test's patcher.
        """

        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        serve_get(monkeypatch, refuse)
        serve_post(monkeypatch, refuse)
