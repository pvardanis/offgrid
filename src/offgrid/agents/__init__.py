"""Adapters for the coding agents that talk to a runtime.

The registry is the one place a name becomes an adapter, and `prepare_agent`
is how a caller asks for that: what a profile names, read as that adapter's own
settings and bound to them. Nothing else is exported beside them — a
re-exported `ClaudeCode` would be indistinguishable, to `import-linter`, from
the import the command line legitimately makes.

The two mappings are keyed alike and go together: one turns the profile's agent
section into a config, the other turns that config into an agent. A name in one
and not the other is a mis-wiring the suite catches.
"""

from offgrid.agent import Agent, AgentName, MakeAgentConfig, Prepare
from offgrid.agents import claude_code
from offgrid.profile import DEFAULT_PATH, Profile

AGENTS: dict[AgentName, Prepare] = {AgentName.CLAUDE_CODE: claude_code.prepare}

AGENT_CONFIGS: dict[AgentName, MakeAgentConfig] = {
    AgentName.CLAUDE_CODE: claude_code.read_config
}


def prepare_agent(profile: Profile, passthrough: tuple[str, ...] = ()) -> Agent:
    """Bind the agent the profile names to what a run has settled for it.

    Each agent gets its own directory, beside the profile and under the name
    it was looked up by, so a second adapter does not inherit the first's. It
    is handed the runtime's address too, because an agent that learns where to
    talk from a config file rather than an environment needs it before
    `configure` runs.

    The arguments are bound here rather than passed to each call that wants
    them, so that what is read to decide whether a run is safe is the same
    thing that is launched. A command with none of its own — `doctor` — binds
    an agent that reports on its configuration alone.

    :param profile: What the agent is called, and what it reads.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.

    :raise ProfileError: When the agent section says something that adapter
        cannot read.
    """
    name = profile.agent.name

    config = AGENT_CONFIGS[name](
        profile.agent,
        host=profile.runtime.host,
        config_dir=DEFAULT_PATH.parent / name.value,
    )

    return AGENTS[name](config, passthrough)
