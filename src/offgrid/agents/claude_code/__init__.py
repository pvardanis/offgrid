"""Claude Code, which speaks Anthropic's message API.

`prepare` is the whole of what the registry asks for. What it answers with is
in `claude_code.py`, and what that writes and reads is beside it.
"""

from pathlib import Path

from offgrid.agent import Agent
from offgrid.agents.claude_code.claude_code import ClaudeCode


def prepare(config_dir: Path) -> Agent:
    """Bind the directory Claude Code keeps its configuration in.

    :param config_dir: Profile directory to use instead of the caller's own,
        which keeps their plugins and servers out of the cached prefix.

    :return: An agent offgrid can configure and start.
    """
    return ClaudeCode(config_dir=config_dir)
