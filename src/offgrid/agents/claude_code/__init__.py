"""Claude Code, which speaks Anthropic's message API.

`read_config` and `prepare` are the whole of what the registry asks for: one
turns the profile's agent section into what Claude Code reads, the other binds
it. What that answers with is in `claude_code.py`, and what it writes and reads
is beside it.
"""

from offgrid.agent import Agent, AgentConfig, AgentName
from offgrid.agents.claude_code.binding import ClaudeCodeConfig, read_config
from offgrid.agents.claude_code.claude_code import ClaudeCode
from offgrid.sections import as_declared

__all__ = ["prepare", "read_config"]


def prepare(config: AgentConfig, passthrough: tuple[str, ...]) -> Agent:
    """Bind what Claude Code is run out of and started with.

    :param config: What the profile and the run settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.

    :raise TypeError: When the config was built for another agent, which is a
        registry binding one name to two adapters.
    """
    own = as_declared(
        config,
        ClaudeCodeConfig,
        adapter=AgentName.CLAUDE_CODE.value,
        registry="agents/__init__.py",
    )

    return ClaudeCode(config_dir=own.config_dir, host=own.host, passthrough=passthrough)
