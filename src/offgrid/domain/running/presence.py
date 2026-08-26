"""Whether the agent a run would start is on this machine, and where it is from.

One function rather than a member on each adapter, because the answer is a
`PATH` lookup and that is the same work whichever agent asked for it: an
adapter answering it for itself is two implementations of one behaviour, and
the day they disagree is the day two surfaces say different things about the
same machine.

Where an agent comes from is a link and never a command to run. An install
command is a fact about somebody else's project — which package manager, which
flags — and it is wrong the moment they change it, with nothing here to notice.
"""

import shutil
from pathlib import Path

from offgrid.domain.running.agent import AgentName

WHERE_AGENTS_COME_FROM = {
    AgentName.CLAUDE_CODE: "https://claude.com/claude-code",
    AgentName.OPENCODE: "https://opencode.ai/",
}
"""The page each agent is published from, for a machine that has not got it."""


def find_agent_on_path(command: str) -> Path | None:
    """Look up the command a launch would run, the way a shell would.

    The `PATH` a run would inherit, so what this answers is what starting the
    agent would find — and a lookup rather than a directory offgrid knows,
    because an agent is installed however its owner installs things.

    :param command: What the agent is started by, as `Agent.command` says it.

    :return: Where it is, or ``None`` where nothing on the `PATH` is it.
    """
    found = shutil.which(command)

    return Path(found) if found is not None else None


def say_where_an_agent_comes_from(name: AgentName) -> str:
    """Name the page an agent is published from.

    :param name: The agent a profile names.

    :return: A sentence naming where to get it.

    :raise KeyError: When offgrid has an adapter for an agent and no page for
        it, which is this module having been left behind rather than a machine
        being short of something.
    """
    return f"Get {name.value} from {WHERE_AGENTS_COME_FROM[name]}."
