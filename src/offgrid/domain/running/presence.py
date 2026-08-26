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
    AgentName.CLAUDE_CODE: "https://docs.claude.com/en/docs/claude-code/setup",
    AgentName.OPENCODE: "https://opencode.ai/docs/",
}
"""Where each agent says to install it from.

The page describing the install rather than the project's front door: whoever
reads this has just been told the machine has not got it, and a landing page
is another click or two from what they came for.
"""


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

    An agent with no page named here says so, rather than refusing. This is
    read while building a report, and a report is where one line failing must
    not take the other lines with it: somebody running `doctor` because the
    runtime is unreachable is owed that answer, not a refusal about offgrid's
    own bookkeeping. `tests/test_architecture.py` is what keeps it from
    happening, and this sentence is what it reads like if that ever fails.

    :param name: The agent a profile names.

    :return: A sentence naming where to get it, or saying that offgrid has
        nowhere to send anybody and is itself at fault.
    """
    published = WHERE_AGENTS_COME_FROM.get(name)

    if published is None:
        return (
            f"offgrid runs {name.value} and has no page to send anybody to for "
            "it, which is a fault in offgrid rather than in this machine."
        )

    return f"Get {name.value} from {published}."
