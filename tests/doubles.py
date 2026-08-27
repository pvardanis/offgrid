"""Stand-ins for what any run talks to: an agent, and the transport under it.

One runtime's server is answered for in `tests/lmstudio_server.py`, beside the
adapter that talks to it, so that a second runtime's stand-in lands beside its
own rather than in here.
"""

from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from pydantic import computed_field

from offgrid.domain.running.agent import (
    AgentConfig,
    AgentName,
    AgentTerms,
    Prepare,
)
from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.leaving import Reading, Status, Subject
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName

CEILING = 262144

# Nowhere on any machine, and named rather than derived: this stand-in is bound
# by a registry rather than out of a config, so it has no directory of its own
# to answer with, and a test reading this back would be reading the double.
KEPT_IN = Path("/nowhere-real/stand-in")


class StandInAgentConfig(AgentConfig):
    """What a second agent adapter's config would be, to whoever wired it.

    Indistinguishable from Claude Code's to a registry dict typed on the base,
    which is the mis-wiring an adapter has to refuse for itself. It carries a
    setting of its own, which is what a second adapter is for.

    :param theme: A setting no other adapter reads.
    """

    theme: str = "dark"

    @computed_field
    @property
    def name(self) -> AgentName:
        """Which agent this is the config for.

        :return: A name offgrid has, so that only the type differs.
        """
        return AgentName.CLAUDE_CODE


class StandInRuntimeConfig(RuntimeConfig):
    """The same for a second runtime adapter, which wires the same way."""

    @computed_field
    @property
    def name(self) -> RuntimeName:
        """Which runtime this is the config for.

        :return: A name offgrid has, so that only the type differs.
        """
        return RuntimeName.LMSTUDIO


@dataclass(frozen=True)
class StandInAgent:
    """An agent offgrid has no adapter for, doing what a test needs.

    :param dialect: What it speaks.
    :param context_floor: The smallest window it can start in.
    :param command: What a launch of it would run.
    :param refusal: What planning a launch raises, where a test wants that.
    """

    dialect: Dialect
    # Its own number and its own command, not the ones the written adapters
    # state: a test that passed on either would be proving nothing about which
    # was asked.
    context_floor: int = 12_000
    command: str = "some-other-agent"
    refusal: Exception | None = None

    @property
    def terms(self) -> AgentTerms:
        """What it states about itself, out of what the test asked for.

        Assembled here rather than taken whole, so a test says only the fact
        it is about and the rest stay at values no written adapter shares.

        :return: The dialect, the floor and the command.
        """
        return AgentTerms(
            dialect=self.dialect,
            context_floor=self.context_floor,
            command=self.command,
        )

    def configure(self) -> None:
        """Write nothing, having nothing to write."""

    def read_what_leaves_this_machine(self) -> tuple[Reading, ...]:
        """Say nothing here could leave, about every subject the port asks about.

        :return: One reading per subject, each saying there is nothing.
        """
        return tuple(
            Reading(subject=way, status=Status.NONE_OFFERED, detail=f"no {way}.")
            for way in Subject
        )

    @property
    def conversations(self) -> Conversations:
        """It keeps them somewhere of offgrid's, having nowhere of its own.

        :return: A directory under offgrid's, and the way back into one.
        """
        return Conversations(
            kept_in=KEPT_IN, resumed_by="`offgrid run -- --resume` opens one."
        )

    def plan(self, model: Model) -> Launch:
        """Answer with a launch, or refuse to build one.

        :param model: The model that would answer.

        :return: A launch that starts nothing.

        :raise Exception: Whatever the test asked to be refused with.
        """
        if self.refusal:
            raise self.refusal

        return Launch(env={}, argv=[self.command])


def answer_as_an_agent(monkeypatch: pytest.MonkeyPatch, agent: StandInAgent) -> None:
    """Answer for an agent nothing on this machine can be made to be.

    The registry is where a name becomes an adapter, so it is where a test
    stands one in. What it arranges — an agent whose floor no model here
    meets, and a launch that cannot be built — has nothing below the adapter
    to arrange it with. A pair that cannot talk is arranged from the runtime
    side, in `tests/pairing.py`, since LM Studio serves both dialects.

    :param monkeypatch: The test's patcher.
    :param agent: What the registry should answer with.
    """
    # Typed, so that a stand-in that has stopped satisfying the port is what
    # the type checker says rather than what a test quietly proves nothing
    # about.
    agents: dict[AgentName, Prepare] = {
        AgentName.CLAUDE_CODE: lambda _config, _passthrough: agent
    }

    monkeypatch.setattr("offgrid.agents.AGENTS", agents)


def serve_get(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Point httpx.get at a transport that answers however the test wants.

    :param monkeypatch: The test's patcher.
    :param handler: Called with the request, answering with a response.
    """
    transport = httpx.MockTransport(handler)

    def get(
        url: str,
        headers: dict | None = None,
        timeout: float = 0,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )

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
