"""Stand-ins for what offgrid talks to: a server, and a Mac."""

import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from pydantic import computed_field

from offgrid.domain.running.agent import AgentConfig, AgentName, Prepare
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName
from offgrid.domain.sizing.machine import Machine
from offgrid.runtimes.lmstudio.holding import MESSAGES, UNLOAD

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
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


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

    Its catalogue, its loads and its releases all come over HTTP, so all three
    are answered for here. Each mapping is a model against the context it is
    served at; a cold model states only its ceiling until something loads it,
    which is what makes the two numbers differ.

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

    def load(identifier: str) -> httpx.Response:
        in_memory[identifier] = True
        asked["loaded"] = identifier
        asked["order"].append(("loaded", identifier))

        return httpx.Response(200, json={"model": identifier, "content": []})

    def let_go(instance: str) -> httpx.Response:
        asked["let_go"].append(instance)
        asked["order"].append(("let_go", instance))

        if not in_memory.get(instance):
            return httpx.Response(
                404,
                json={
                    "error": {
                        "type": "model_not_found",
                        "message": f"Model with instance identifier "
                        f"'{instance}' is not loaded.",
                    }
                },
            )

        in_memory[instance] = False

        return httpx.Response(200, json={"instance_id": instance})

    def posted(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)

        if request.url.path == UNLOAD:
            return let_go(body["instance_id"])

        return load(body["model"])

    serve_get(monkeypatch, catalogue)
    serve_post(monkeypatch, posted)

    return asked


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
    _take_over(monkeypatch, MESSAGES, lambda body: answer(body["model"]))


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

    if getattr(serving, "__module__", None) != __name__:
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
