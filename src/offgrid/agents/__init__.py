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


def prepare_agent(profile: Profile) -> Agent:
    """Bind the agent the profile names to where it keeps its configuration.

    Each agent gets its own directory, beside the profile and under the name
    it was looked up by, so a second adapter does not inherit the first's.

    :param profile: What the agent is called.

    :return: An agent offgrid can configure and start.
    """
    return AGENTS[profile.agent](DEFAULT_PATH.parent / profile.agent.value)
