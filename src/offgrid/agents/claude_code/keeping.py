"""Where a Claude Code run leaves the conversation, and how to open it again.

Its own module for the reason the two readings beside it have theirs: this is
settled somewhere else entirely. No file decides it and no argument moves it —
the whole of the answer is the directory the launch points the agent at.
"""

from pathlib import Path

from offgrid.domain.running.keeping import Conversations

# What `claude --help` offers at the version below: `-r, --resume [value]`,
# which resumes by session ID or opens a picker over what is there.
RESUME = "--resume"

# `CLAUDE_CONFIG_DIR` decides where conversations are written as well as where
# settings are read, measured against the version below: pointing it at
# offgrid's own directory moved every conversation there with it, which is why
# `claude --resume <id>` outside a run answers "No conversation found with
# session ID" for a session offgrid started minutes earlier. claude 2.1.246 has
# no argument or variable separating the two, so this is a fact about the
# directory rather than a choice offgrid makes twice.
MEASURED_AGAINST = "claude 2.1.246"


def read_where_conversations_are_kept(config_dir: Path) -> Conversations:
    """Say where a run leaves the conversation, and how to get back into one.

    The directory offgrid points the agent at rather than the layout beneath
    it: the `projects/` a transcript lands under is Claude Code's own, and
    naming it here would be offgrid claiming something it does not settle.

    :param config_dir: The directory the agent is run out of.

    :return: Where they are kept, and the way back in.
    """
    return Conversations(
        kept_in=config_dir,
        resumed_by=(
            f"`offgrid run -- {RESUME}` opens a picker over these and "
            f"`offgrid run -- {RESUME} <id>` opens one by session. Measured "
            f"against {MEASURED_AGAINST}, `CLAUDE_CONFIG_DIR` carries "
            "conversations as well as settings, so `claude` started outside a "
            "run reads a different directory and finds none of them."
        ),
    )
