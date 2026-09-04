"""A runtime serving exactly the dialects a test says, for the pair that is refused.

LM Studio, the one runtime offgrid has an adapter for, serves both dialects,
so a pair that cannot talk has nothing below the adapter to arrange it with —
which is what this is for. Everything asked over the wire refuses here, so a test that
reaches one of those says so rather than passing on an invented answer; a test
wanting those answers stands LM Studio's own server in instead.
"""

from dataclasses import dataclass

import pytest

from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.runtime import Connect, RuntimeName


@dataclass(frozen=True)
class StandInRuntime:
    """A runtime whose dialects a test states.

    `let_go` raises where the port says an adapter owes an answer, which is
    deliberate: a test reaching cleanup with this stood in has already gone
    past the refusal it was written for, and a masked outcome there would be
    worse than a loud one. Nothing reaches it while the pairing check refuses
    before a load.

    :param dialects: What it serves.
    :param downloaded: What its catalogue answers, or ``None`` to refuse being
        asked. A screen reads the catalogue before it reports on any pairing,
        so a refusal that is settled before a load still needs one; a command
        that reaches it has gone past a refusal and is told so.
    :param holding: Which of them it has in memory.
    """

    dialects: frozenset[Dialect]
    downloaded: tuple[Model, ...] | None = None
    holding: tuple[Model, ...] = ()

    def read_catalogue(self) -> list[Model]:
        """Answer with the catalogue a test stated, or refuse having none.

        :return: What it has.

        :raise AssertionError: When the test stated no catalogue.
        """
        if self.downloaded is None:
            raise AssertionError(
                "the stand-in runtime was asked to read the catalogue, after the "
                "pairing check `run` settles before anything is reached. Assert "
                "on the refusal rather than on what a run would have loaded."
            )

        return list(self.downloaded)

    def read_held(self) -> list[Model]:
        """Answer with what is in memory, or refuse where no catalogue was stated.

        Holding nothing is an answer; having stated no catalogue at all is what
        refuses, because that is a test reaching past a refusal it was written
        for rather than a runtime with an empty pool.

        :return: What is in memory, which may be nothing.

        :raise AssertionError: When the test stated no catalogue.
        """
        if self.downloaded is None:
            raise AssertionError(
                "the stand-in runtime was asked to read what it holds, after the "
                "pairing check `run` settles before anything is reached. Assert "
                "on the refusal rather than on what a run would have loaded."
            )

        return list(self.holding)

    def ensure_only(self, model_request: ModelRequest) -> Model:
        """Refuse, having nothing to hold a model in.

        :param model_request: What would have been held.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            f"the stand-in runtime was asked to hold {model_request.identifier}, "
            "after the "
            "pairing check `run` settles before anything is reached. Assert "
            "on the refusal rather than on what a run would have loaded."
        )

    def let_go(self, identifier: str) -> bool:
        """Refuse, holding nothing to let go of.

        :param identifier: What would have been let go of.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            f"the stand-in runtime was asked to let {identifier} go, after the "
            "pairing check `run` settles before anything is reached. Assert "
            "on the refusal rather than on what a run would have loaded."
        )


def answer_as_a_runtime(
    monkeypatch: pytest.MonkeyPatch, runtime: StandInRuntime
) -> None:
    """Answer for a runtime serving less than the ones offgrid has adapters for.

    The registry is where a name becomes an adapter, so it is where a test
    stands one in.

    :param monkeypatch: The test's patcher.
    :param runtime: What the registry should answer with.
    """
    # Typed, so that a stand-in that has stopped satisfying the port is what
    # the type checker says rather than what a test quietly proves nothing
    # about.
    runtimes: dict[RuntimeName, Connect] = {
        RuntimeName.LMSTUDIO: lambda _config: runtime
    }

    monkeypatch.setattr("offgrid.runtimes.RUNTIMES", runtimes)
