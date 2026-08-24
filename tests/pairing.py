"""A runtime serving exactly the dialects a test says, for the pair that is refused.

Every runtime offgrid has an adapter for serves both dialects, so a pair that
cannot talk has nothing below the adapter to arrange it with — which is what
this is for. Everything asked over the wire refuses here, so a test that
reaches one of those says so rather than passing on an invented answer; a test
wanting those answers stands LM Studio's own server in instead.
"""

from dataclasses import dataclass, field

import pytest

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.runtime import Connect, RuntimeName

# Its own answers rather than the written adapter's: a test that passed on
# either would be proving nothing about which of them was asked. Nothing here
# reads them — they are what satisfies the port beside the dialects a test
# states.
CAPABILITIES = Capabilities(
    counts_tokens=True,
    release_can_be_commanded=False,
    manages_its_own_memory=False,
)


@dataclass(frozen=True)
class StandInRuntime:
    """A runtime whose dialects a test states.

    :param dialects: What it serves.
    """

    dialects: frozenset[Dialect]
    capabilities: Capabilities = field(init=False, default=CAPABILITIES)

    def read_catalogue(self) -> list[Model]:
        """Refuse, having no catalogue to answer with.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            "the stand-in runtime was asked to read the catalogue, after a check "
            "that settles before anything is reached. Assert on the "
            "refusal rather than on what a run would have loaded."
        )

    def read_held(self) -> list[Model]:
        """Refuse, holding nothing to answer with.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            "the stand-in runtime was asked to read what it holds, after a check "
            "that settles before anything is reached. Assert on the "
            "refusal rather than on what a run would have loaded."
        )

    def ensure_only(self, model_request: ModelRequest) -> Model:
        """Refuse, having nothing to hold a model in.

        :param model_request: What would have been held.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            "the stand-in runtime was asked to hold a model, after a check "
            "that settles before anything is reached. Assert on the "
            "refusal rather than on what a run would have loaded."
        )

    def let_go(self, identifier: str) -> bool:
        """Refuse, holding nothing to let go of.

        :param identifier: What would have been let go of.

        :raise AssertionError: Always.
        """
        raise AssertionError(
            "the stand-in runtime was asked to let a model go, after a check "
            "that settles before anything is reached. Assert on the "
            "refusal rather than on what a run would have loaded."
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
