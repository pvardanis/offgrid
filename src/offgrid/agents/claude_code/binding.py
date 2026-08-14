"""What Claude Code is bound to before a run starts, and where it comes from.

Two of the three are offgrid's to settle rather than the profile's: the
directory the agent is given, and the address of the runtime it will talk to.
The section says the rest, and says nothing else — a key Claude Code does not
read is a typo to report.
"""

from pathlib import Path

from pydantic import ConfigDict

from offgrid.agent import AgentConfig, AgentName
from offgrid.sections import read_section


class ClaudeCodeConfig(AgentConfig):
    """Everything Claude Code is run out of, once a run has settled it.

    :param name: Always ``claude-code``.
    :param config_dir: Where its settings and its notes are kept.
    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: AgentName = AgentName.CLAUDE_CODE
    config_dir: Path
    host: str


def read_config(
    section: AgentConfig, *, host: str, config_dir: Path
) -> ClaudeCodeConfig:
    """Read the profile's agent section as Claude Code's own settings.

    :param section: What the profile says about the agent.
    :param host: Address the runtime listens on.
    :param config_dir: Where this agent's own configuration is kept.

    :return: What the adapter is built from.

    :raise ProfileError: When the section says something Claude Code cannot
        read.
    """
    return read_section(
        section,
        ClaudeCodeConfig,
        port="agent",
        settled={"host": host, "config_dir": config_dir},
    )
