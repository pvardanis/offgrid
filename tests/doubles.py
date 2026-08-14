"""Stand-ins for what offgrid talks to: a server, a runtime's tool, a Mac."""

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from pydantic import computed_field

from offgrid.domain.agent import AgentConfig, AgentName, Prepare
from offgrid.domain.dialect import Dialect
from offgrid.domain.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.launch import Launch
from offgrid.domain.machine import Machine
from offgrid.domain.model import Model
from offgrid.domain.runtime import RuntimeConfig, RuntimeName

GIB = 1024**3
MACHINE = Machine(
    chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
)
CEILING = 262144


def answer_as_a_mac(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Answer with a fixed machine, and write nowhere real.

    :param monkeypatch: The test's patcher.
    :param tmp_path: Where the profile goes, and the agent's directory beside
        it.
    """
    monkeypatch.setattr("offgrid.cli.detect", lambda: MACHINE)

    # Both, because each module holds its own name for it: the command line
    # reads and writes the profile, and an agent's config derives its own
    # directory. A test that patched one would reach the real other.
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.domain.agent.OFFGRID_HOME", tmp_path)


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
    :param refusal: What planning a launch raises, where a test wants that.
    """

    dialect: Dialect
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


def _entry(identifier: str, *, served: int, ceiling: int, in_memory: bool) -> dict:
    """Describe one model the way LM Studio's catalogue does.

    :param identifier: The model's id.
    :param served: The context it is served at once it is loaded.
    :param ceiling: The context it states before anything loads it.
    :param in_memory: Whether it is held.

    :return: One catalogue entry.
    """
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": ceiling,
    }
    if in_memory:
        entry["loaded_context_length"] = served

    return entry


def answer_as_lm_studio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    holding: dict[str, int] | None = None,
    cold: dict[str, int] | None = None,
    ceiling: int = CEILING,
) -> dict:
    """Answer for LM Studio, as what it holds changes.

    Its catalogue and its loads come over HTTP and it lets go through its own
    tool, so all three are answered for here. Each mapping is a model against
    the context it is served at; a cold model states only its ceiling until
    something loads it, which is what makes the two numbers differ.

    :param monkeypatch: The test's patcher.
    :param holding: Models in memory, against the context each is served at.
    :param cold: Models it has and is not holding.
    :param ceiling: The context every model states before it is loaded.

    :return: What it was asked to load and let go of, and in what order.
    """
    served = {**(holding or {}), **(cold or {})}
    in_memory = dict.fromkeys(holding or {}, True) | dict.fromkeys(cold or {}, False)
    asked: dict = {"loaded": None, "let_go": [], "order": []}

    def catalogue(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    _entry(name, served=served[name], ceiling=ceiling, in_memory=state)
                    for name, state in in_memory.items()
                ]
            },
        )

    def load(request: httpx.Request) -> httpx.Response:
        identifier = json.loads(request.content)["model"]
        in_memory[identifier] = True
        asked["loaded"] = identifier
        asked["order"].append(("loaded", identifier))

        return httpx.Response(200, json={"model": identifier, "content": []})

    def tool(argv: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
        identifier = argv[2]
        in_memory[identifier] = False
        asked["let_go"].append(identifier)
        asked["order"].append(("let_go", identifier))

        return subprocess.CompletedProcess(list(argv), 0, "", "")

    serve_get(monkeypatch, catalogue)
    serve_post(monkeypatch, load)
    monkeypatch.setattr(subprocess, "run", tool)

    return asked


def refuse_to_let_go(monkeypatch: pytest.MonkeyPatch, complaint: str) -> None:
    """Answer as a runtime whose tool will not let go of anything.

    :param monkeypatch: The test's patcher.
    :param complaint: What the tool says about it.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            list(argv), 1, "", complaint
        ),
    )


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
