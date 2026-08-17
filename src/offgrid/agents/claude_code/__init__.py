"""Claude Code, which speaks Anthropic's message API.

`ClaudeCodeConfig` and `prepare` are the whole of what the registry asks for:
one says what a profile's agent section may hold, the other binds it. What
that answers with is in `claude_code.py`, and what it writes and reads is
beside it.
"""

from offgrid.agents.claude_code.claude_code import ClaudeCode
from offgrid.agents.claude_code.config import ClaudeCodeConfig
from offgrid.domain.running.agent import Agent, AgentConfig, Passthrough
from offgrid.shared.declaring import as_declared


def prepare(config: AgentConfig, passthrough: Passthrough) -> Agent:
    """Bind what Claude Code is run out of and started with.

    :param config: What the profile settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: An agent offgrid can configure and start.

    :raise TypeError: When the config was built for another agent, which is a
        registry binding one name to two adapters.
    """
    return ClaudeCode(
        config=as_declared(config, ClaudeCodeConfig), passthrough=passthrough
    )
