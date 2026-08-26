"""What offgrid asks of an agent, and which ones there are.

An adapter binds its own settings once and answers with something satisfying
``Agent``. Its two attributes are settled when that happens — both facts about
the agent itself, neither of them anyone's to choose; its four methods act —
three on the configuration, one on nothing at all.

Why it is shaped this way is in `docs/architecture.md` under "The agent seam".
"""

from abc import abstractmethod
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, computed_field

from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.leaving import Reading
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

        An edit is left alone: a run is no place to lose one — including an
        edit leaving something able to reach off this machine, which the
        reading below reports and this call has no business writing over. What
        decides is whether the file holds an edit, not whether it is there; see
        `config_editing.py`.

        :raise AgentSettingsError: When it cannot be read, or cannot be written.
        """
        ...

    def read_what_leaves_this_machine(self) -> tuple[Reading, ...]:
        """Say what this run could send off this machine, one way at a time.

        Its own member rather than part of configuring, because the failures
        it describes are silent: a hosted tool called against a model held
        here comes back as an invented answer, and a published transcript
        leaves while the run works exactly as asked.

        One reading per subject rather than one answer, because those are
        fixed in different files by different edits, and a refusal that could
        not say which it was about would send a person to read both. Every
        subject in `Subject` is answered, an agent that has no such thing
        included: that answer is `NONE_OFFERED` with the evidence for it.

        It answers rather than refuses, so one reading serves both the command
        that must not proceed and the one that only reports; it reads arguments
        as well as configuration, writes nothing, and its remedy is words.

        :return: One reading for each way off this machine, saying what was
            found and what to change.

        :raise AgentSettingsError: When the configuration is there and cannot
            be read at all, which is no answer about any of them.
        """
        ...

    def read_where_conversations_are_kept(self) -> Conversations:
        """Say where a conversation this run starts is kept, and the way back.

        Its own member rather than a subject on the reading above, because
        nothing here left the machine: this is where finished files sit, which
        is a hazard of its own — a person who cannot find a session they had
        minutes ago is told the transcript is gone.

        A run is its own installation, so what an adapter answers with is a
        directory of offgrid's rather than the one the agent reads when a
        person starts it themselves. What that costs them is the adapter's to
        say, in its own terms and against the version it measured.

        Nothing decides it at read time and there is no state to be in, so it
        answers rather than refuses, writes nothing, and holds for a machine
        that has never run the agent.

        :return: Where they are kept, and how to open one again.

        :raise ValueError: When the adapter answers with a relative directory
            or names no way back in, which is an adapter being wrong rather
            than a machine.
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
