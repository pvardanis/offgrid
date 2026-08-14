"""Adapters for the coding agents that talk to a runtime.

The registry is the one place a name becomes an adapter. `create_agent_config`
turns what a profile says into what one adapter reads, and `prepare_agent`
binds that. Nothing else is exported beside them — a re-exported `ClaudeCode`
would be indistinguishable, to `import-linter`, from the import the command
line legitimately makes.

The two mappings are keyed alike and go together: one says what a name is
built from, the other what it is started as.
"""

from pydantic import ValidationError

from offgrid.agent import Agent, AgentConfig, AgentName, Prepare
from offgrid.agents import claude_code
from offgrid.exceptions import ProfileError
from offgrid.profile import describe_problems

AGENTS: dict[AgentName, Prepare] = {AgentName.CLAUDE_CODE: claude_code.prepare}

AGENT_CONFIGS: dict[AgentName, type[AgentConfig]] = {
    AgentName.CLAUDE_CODE: claude_code.ClaudeCodeConfig
}


def create_agent_config(said: dict, *, runtime_host: str) -> AgentConfig:
    """Read a profile's agent section as the adapter it names reads it.

    The runtime's address is supplied rather than read, because it belongs to
    the other section: an agent that writes where to talk into a config file
    of its own needs it before `configure` runs.

    :param said: What the profile says about the agent.
    :param runtime_host: Address the runtime listens on.

    :return: What that adapter is built from.

    :raise ProfileError: When the name is not one offgrid has an adapter for,
        or the section says something that adapter cannot read.
    """
    written = {key: value for key, value in said.items() if key != "name"}

    try:
        name = AgentName(said.get("name", AgentName.CLAUDE_CODE.value))
    except ValueError as error:
        raise ProfileError(
            f"The `agent` section names {said['name']}, which offgrid has no "
            f"adapter for. It has {', '.join(one.value for one in AgentName)}."
        ) from error

    try:
        return AGENT_CONFIGS[name](**written, runtime_host=runtime_host)
    except (TypeError, ValidationError) as error:
        raise ProfileError(
            f"{name.value} cannot read the `agent` section of the profile: "
            f"{_said_about(error)}. Take it out of the file, or spell it the "
            "way that adapter does."
        ) from error


def prepare_agent(config: AgentConfig, passthrough: tuple[str, ...] = ()) -> Agent:
    """Bind the agent the config is for to what a run has settled for it.

    Looked up by the config's own name, so a config cannot reach an adapter
    that would misread it.

    The arguments are bound here rather than passed to each call that wants
    them, so that what is read to decide whether a run is safe is the same
    thing that is launched. A command with none of its own — `doctor` — binds
    an agent that reports on its configuration alone.

    :param config: What the profile settled for the agent.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.
    """
    return AGENTS[config.name](config, passthrough)


def _said_about(error: Exception) -> str:
    """Say what refused a section, whichever way it was refused.

    A section naming something offgrid settles arrives as a `TypeError` about
    a repeated argument, which is true and unreadable.

    :param error: What refusing it raised.

    :return: What to tell whoever typed the section.
    """
    if isinstance(error, ValidationError):
        return describe_problems(error)

    return f"{error}, which offgrid settles itself"
