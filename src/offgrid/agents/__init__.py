"""Adapters for the coding agents that talk to a runtime.

The registry is the one place a name becomes an adapter, and `prepare_agent`
is how a caller asks for that: what a profile names, bound to the directory
its configuration lives in. Nothing else is exported beside them — a
re-exported `ClaudeCode` would be indistinguishable, to `import-linter`, from
the import the command line legitimately makes.
"""

from offgrid.agent import Agent, AgentName, Prepare
from offgrid.agents import claude_code
from offgrid.profile import DEFAULT_PATH, Profile

AGENTS: dict[AgentName, Prepare] = {AgentName.CLAUDE_CODE: claude_code.prepare}


def prepare_agent(profile: Profile, passthrough: tuple[str, ...] = ()) -> Agent:
    """Bind the agent the profile names to what a run has settled for it.

    Each agent gets its own directory, beside the profile and under the name
    it was looked up by, so a second adapter does not inherit the first's.

    The arguments are bound here rather than passed to each call that wants
    them, so that what is read to decide whether a run is safe is the same
    thing that is launched. A command with none of its own — `doctor` — binds
    an agent that reports on its configuration alone.

    :param profile: What the agent is called.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.
    """
    return AGENTS[profile.agent](DEFAULT_PATH.parent / profile.agent.value, passthrough)
