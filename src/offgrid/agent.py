"""What offgrid asks of an agent, and which ones there are.

An adapter binds a configuration directory once and answers with something
satisfying ``Agent``. Its one attribute is settled when that happens; its
three methods act — two on the configuration, one on nothing at all.

Why it is shaped this way is in `docs/architecture.md` under "The agent seam".
"""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from offgrid.dialect import Dialect
from offgrid.launch import Launch
from offgrid.model import Model


class AgentName(Enum):
    """An agent offgrid has an adapter for.

    What a profile may name. The registry in ``agents/`` binds each of these
    to the adapter that answers for it.
    """

    CLAUDE_CODE = "claude-code"


class Agent(Protocol):
    """An agent offgrid can start against a model on this machine."""

    @property
    def dialect(self) -> Dialect:
        """The API shape the agent speaks.

        :return: The dialect a runtime has to serve for the pair to work.
        """
        ...

    def configure(self) -> None:
        """Write what the agent needs and does not have.

        What is already there is left alone: a configuration is meant to be
        edited, and a run is no place to lose those edits — including an edit
        the guard below refuses, which is that call's to report.

        :raise AgentSettingsError: When what is missing cannot be written.
        """
        ...

    def require_hosted_tools_denied(self) -> None:
        """Refuse a configuration that lets the agent reach a hosted tool.

        Its own job rather than part of configuring, because the failure it
        prevents is silent: a tool that runs on its vendor's servers has
        nothing to run it against a model on this machine, so the model emits
        the call as prose and the agent returns that as a result — an invented
        answer, with no error anywhere.

        :raise AgentSettingsError: When the configuration permits one, is not
            there to say otherwise, or cannot be read.
        """
        ...

    def plan(
        self,
        model: Model,
        *,
        host: str,
        token: str,
        passthrough: list[str],
    ) -> Launch:
        """Work out how to start the agent against a model.

        It writes nothing. Agents configure themselves in ways that have
        nothing in common — an environment, a provider block, a table in a
        config file — and that belongs in `configure`, where a caller can see
        it happen, rather than in the call that builds an argument list.

        :param model: The model that will answer.
        :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
        :param token: Credential the local server ignores but the agent
            requires.
        :param passthrough: Arguments handed to the agent unchanged.

        :return: The environment and command to run.
        """
        ...


Prepare = Callable[[Path], Agent]
