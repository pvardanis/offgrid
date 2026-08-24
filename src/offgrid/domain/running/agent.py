"""What offgrid asks of an agent, and which ones there are.

An adapter binds its own settings once and answers with something satisfying
``Agent``. Its two attributes are settled when that happens — both facts about
the agent itself, neither of them anyone's to choose; its three methods act —
two on the configuration, one on nothing at all.

Why it is shaped this way is in `docs/architecture.md` under "The agent seam".
"""

from abc import abstractmethod
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, computed_field

from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.shared.home import OFFGRID_HOME


class AgentName(Enum):
    """An agent offgrid has an adapter for.

    What a profile may name. The registry in ``agents/`` binds each of these
    to the adapter that answers for it.
    """

    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"


class AgentConfig(BaseModel):
    """What one agent adapter is built from.

    Abstract, and each adapter declares its own. Which one a profile gets is
    the registry's answer to the name it holds, so ``name`` is a property of
    the class rather than a field a file sets — an adapter cannot be handed a
    config claiming to be another.

    Keys it does not name are refused, so a typo under ``agent:`` is reported
    rather than dropped.

    :param runtime_host: Address the runtime listens on. Offgrid settles it
        from the runtime's own section, so the file neither says it nor has it
        written back; an agent that writes where to talk into a config file of
        its own needs it before ``configure`` runs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_host: str = Field(exclude=True)

    @computed_field
    @property
    @abstractmethod
    def name(self) -> AgentName:
        """Which agent this is the config for.

        Computed, so that it survives a round trip through the profile: what
        is written is what picks this class again when the file is read.

        :return: The name a profile calls this adapter by.
        """

    @property
    def config_dir(self) -> Path:
        """Where this agent's own configuration is kept.

        Beside the profile and under the agent's own name, so a second adapter
        does not inherit the first's. Derived rather than stored: nobody says
        it, so nothing can disagree about it.

        :return: The directory the agent is run out of.
        """
        return OFFGRID_HOME / self.name.value


class Agent(Protocol):
    """An agent offgrid can start against a model on this machine."""

    @property
    def dialect(self) -> Dialect:
        """The API shape the agent speaks.

        :return: The dialect a runtime has to serve for the pair to work.
        """
        ...

    @property
    def context_floor(self) -> int:
        """The smallest window this agent can start in.

        A fact about the agent rather than a preference, so nothing outside it
        may say otherwise: an agent whose system prompt and tool definitions
        do not fit fails at startup, and asserting a smaller number only buys
        that failure after a load has been paid for.

        :return: The window below which it will not start, in tokens.
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

        :return: The environment and command to run, what to take back out of
            what the agent inherits, and anything a person is owed before it
            starts — nothing, for an agent with nothing to say.
        """
        ...


Passthrough = tuple[str, ...]
"""Arguments handed to the agent unchanged, as they were typed."""

Prepare = Callable[[AgentConfig, Passthrough], Agent]
