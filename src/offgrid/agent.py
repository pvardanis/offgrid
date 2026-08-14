"""What offgrid asks of an agent, and which ones there are.

An adapter binds its own settings once and answers with something satisfying
``Agent``. Its one attribute is settled when that happens; its three methods
act — two on the configuration, one on nothing at all.

Why it is shaped this way is in `docs/architecture.md` under "The agent seam".
"""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from offgrid.dialect import Dialect
from offgrid.hosted_tools import HostedToolsReport
from offgrid.launch import Launch
from offgrid.model import Model


class AgentName(Enum):
    """An agent offgrid has an adapter for.

    What a profile may name. The registry in ``agents/`` binds each of these
    to the adapter that answers for it.
    """

    CLAUDE_CODE = "claude-code"


class AgentConfig(BaseModel):
    """The profile's agent section, as much of it as offgrid itself reads.

    Extra keys are carried rather than refused, because the section belongs to
    whichever adapter the name picks and this type cannot know what that one
    reads. The registry narrows it to that adapter's own config, which forbids
    what it does not name.

    :param name: Which agent adapter to use.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    name: AgentName = AgentName.CLAUDE_CODE


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
        that leaves a hosted tool reachable, which the reading below reports
        and this call has no business overwriting.

        :raise AgentSettingsError: When what is missing cannot be written.
        """
        ...

    def read_hosted_tools(self) -> HostedToolsReport:
        """Say what this agent can reach that offgrid cannot run here.

        Its own member rather than part of configuring, because the failure
        it describes is silent: a tool that runs on its vendor's servers has
        nothing to run it against a model on this machine, so the model emits
        the call as prose and the agent returns that as a result — an
        invented answer, with no error anywhere.

        It answers rather than refuses, so that one reading serves both the
        command that must not proceed and the command that only reports. It
        reads the arguments as well as the configuration, because a
        configuration only denies where the agent loads it, and an agent
        takes arguments deciding whether it does.

        It writes nothing and changes nothing. Rewriting a configuration
        would overrule an edit a person made deliberately, and dropping an
        argument would launch something other than what they typed — so the
        remedy it carries is words rather than an action.

        :return: What it found, and what to change.

        :raise AgentSettingsError: When the configuration is there and cannot
            be read at all, which is not an answer about hosted tools.
        """
        ...

    def plan(self, model: Model) -> Launch:
        """Work out how to start the agent against a model.

        It writes nothing. Agents configure themselves in ways that have
        nothing in common — an environment, a provider block, a table in a
        config file — and that belongs in `configure`, where a caller can see
        it happen, rather than in the call that builds an argument list.

        The model is the only thing it takes, because it is the only thing a
        run discovers. Everything else the agent needs was settled before it
        started, and is bound to the adapter rather than passed here.

        :param model: The model that will answer.

        :return: The environment and command to run.
        """
        ...


Prepare = Callable[[AgentConfig, tuple[str, ...]], Agent]


class MakeAgentConfig(Protocol):
    """Turn the profile's agent section into one adapter's own settings."""

    def __call__(
        self, section: AgentConfig, *, host: str, config_dir: Path
    ) -> AgentConfig:
        """Read the section, alongside what offgrid settles for every agent.

        The two settled arguments are what an adapter cannot read out of its
        own section: where the runtime listens, which the runtime section
        says, and the directory offgrid gives it, which is derived from where
        the profile lives. An agent that writes a config file rather than
        taking an environment needs the first of them before `configure` runs.

        :param section: What the profile says about the agent.
        :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
        :param config_dir: Where this agent's own configuration is kept.

        :return: The config the adapter it names is built from.

        :raise ProfileError: When the section says something that adapter
            cannot read.
        """
        ...
