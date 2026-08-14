"""Claude Code, which speaks Anthropic's message API.

`ClaudeCodeConfig` and `prepare` are the whole of what the registry asks for:
one says what a profile's agent section may hold, the other binds it. What
that answers with is in `claude_code.py`, and what it writes and reads is
beside it.
"""

from offgrid.agent import Agent, AgentConfig
from offgrid.agents.claude_code.binding import ClaudeCodeConfig
from offgrid.agents.claude_code.claude_code import ClaudeCode

__all__ = ["ClaudeCodeConfig", "prepare"]


def prepare(config: AgentConfig, passthrough: tuple[str, ...]) -> Agent:
    """Bind what Claude Code is run out of and started with.

    :param config: What the profile settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.

    :raise TypeError: When the config was built for another agent, which is a
        registry binding one name to two adapters.
    """
    if not isinstance(config, ClaudeCodeConfig):
        raise TypeError(
            f"claude-code was handed {type(config).__name__}, which is not its "
            "own config. In agents/__init__.py, the name is bound to one "
            "adapter's config and another adapter's factory."
        )

    return ClaudeCode(config=config, passthrough=passthrough)
