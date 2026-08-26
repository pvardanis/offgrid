"""Where a Claude Code run leaves the conversation, and how to open it again.

Its own module for the reason the two readings beside it have theirs: this is
settled somewhere else entirely. No file decides it and no argument moves it —
the whole of the answer is the directory the launch points the agent at.
"""

from pathlib import Path

from offgrid.domain.running.conversations import Conversations

# What `claude --help` offers at the version below: `-r, --resume [value]`,
# "Resume a conversation by session ID, or open interactive picker with
# optional search term".
RESUME = "--resume"
OFFERS_RESUME = "claude 2.1.246"

# `CLAUDE_CONFIG_DIR` decides where conversations are written as well as where
# settings are read, measured against the version below and recorded in
# `docs/decisions.md`: pointing it at offgrid's own directory moved every
# conversation there with it, which is why `claude --resume <id>` outside a run
# answers "No conversation found with session ID" for a session offgrid started
# minutes earlier. No argument or variable separates where conversations are
# written from where settings are read, so it is a fact about the directory
# rather than a choice offgrid makes twice.
#
# The two stamps differ because the readings do: one off `--help`, one from a
# run that moved the directory. Stamping both with either would claim a reading
# nobody took.
CARRIES_CONVERSATIONS = "claude 2.1.245"


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
            f"`offgrid run -- {RESUME} <id>` opens one by session, measured "
            f"against {OFFERS_RESUME}. Measured against {CARRIES_CONVERSATIONS}, "
            "`CLAUDE_CONFIG_DIR` carries conversations as well as settings, "
            "which is what moved them here."
        ),
    )
