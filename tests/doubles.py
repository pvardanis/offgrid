"""Stand-ins for what any run talks to: a Mac, an agent, and the transport.

One runtime's server is answered for in `tests/lmstudio_server.py`, beside the
adapter that talks to it, so that a second runtime's stand-in lands beside its
own rather than in here.
"""

from dataclasses import dataclass

import httpx
import pytest
from pydantic import computed_field

from offgrid.domain.running.agent import AgentConfig, AgentName, Prepare
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName

CEILING = 262144


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
    :param refusal: What planning a launch raises, where a test wants that.
    """

    dialect: Dialect
    # Its own number, not the one the written adapter states: a test that
    # passed on either would be proving nothing about which was asked.
    context_floor: int = 12_000
    refusal: Exception | None = None

    def configure(self) -> None:
        """Write nothing, having nothing to write."""

    def read_hosted_tools(self) -> HostedToolsReport:
        """Answer that there is nothing to reach, having no tools at all.

        :return: What an agent with no hosted tool says.
        """
        return HostedToolsReport(
            status=HostedToolsStatus.NONE_OFFERED,
            detail="a stand-in offers no tool that runs anywhere else.",
        )

    def plan(self, model: Model) -> Launch:
        """Answer with a launch, or refuse to build one.

        :param model: The model that would answer.

        :return: A launch that starts nothing.

        :raise Exception: Whatever the test asked to be refused with.
        """
        if self.refusal:
            raise self.refusal

        return Launch(env={}, argv=["claude"])


def answer_as_an_agent(monkeypatch: pytest.MonkeyPatch, agent: StandInAgent) -> None:
    """Answer for an agent nothing on this machine can be made to be.

    The registry is where a name becomes an adapter, so it is where a test
    stands one in. Both of the things this arranges — an agent speaking a
    dialect no runtime here serves, and a launch that cannot be built — have
    nothing below the adapter to arrange them with.

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
