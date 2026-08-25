"""What a Claude Code run could send off this machine, read out of what it loads.

Two subjects and two places to read them, so each has a module of its own and
this one asks both. WebSearch is settled by a settings file and by the argument
deciding whether that file is loaded at all, in `hosted_tools.py`; putting the
session on Anthropic's servers is settled by the command line alone, in
`publishing.py`.
"""

from pathlib import Path

from offgrid.agents.claude_code.hosted_tools import read_hosted_tools
from offgrid.agents.claude_code.publishing import read_transcript_sharing
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.leaving import Reading


def read_what_leaves_this_machine(
    settings: Path, passthrough: Passthrough
) -> tuple[Reading, ...]:
    """Say what this Claude Code run could send off this machine.

    :param settings: The settings file offgrid writes for this agent.
    :param passthrough: What was handed to the agent unchanged.

    :return: One reading for each way off this machine.

    :raise AgentSettingsError: When the settings are there and cannot be read.
    """
    return (
        read_hosted_tools(settings, passthrough),
        read_transcript_sharing(passthrough),
    )
