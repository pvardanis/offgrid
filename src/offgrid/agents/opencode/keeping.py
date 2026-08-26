"""Where an OpenCode run leaves the conversation, and how to open it again.

Its own module for the reason the two readings beside it have theirs: nothing
in the file offgrid writes decides this. A session lands in the store the
launch points `XDG_DATA_HOME` at, and that variable is the whole of the answer.
"""

from pathlib import Path

from offgrid.domain.running.keeping import Conversations

# What `opencode run --help` and `opencode session --help` offer at the version
# below: `-c, --continue` takes up the last session, `-s, --session <id>` takes
# up one by identifier, and `opencode session list` names what is there.
CONTINUE = "--continue"
SESSION = "--session"
LISTING = "session list"

# Measured on the version below, against a store nothing had written to: all
# three read the database under the directory `XDG_DATA_HOME` names, and
# `session list` there answered with nothing while the same command outside a
# run listed a person's own sessions. So which store is read is settled by what
# a run sets and by nothing else.
MEASURED_AGAINST = "opencode 1.18.23"


def read_where_conversations_are_kept(store: Path) -> Conversations:
    """Say where a run leaves the conversation, and how to get back into one.

    The store offgrid points the agent at rather than the layout beneath it:
    the `opencode/` that OpenCode hangs off this value, and the database and
    write-ahead log inside it, are OpenCode's own.

    :param store: What the launch points `XDG_DATA_HOME` at.

    :return: Where they are kept, and the way back in.
    """
    return Conversations(
        kept_in=store,
        resumed_by=(
            f"`offgrid run -- run {CONTINUE}` takes up the last one, "
            f"`offgrid run -- run {SESSION} <id>` one by identifier, and "
            f"`offgrid run -- {LISTING}` names what is there. Measured against "
            f"{MEASURED_AGAINST}, all three read the store `XDG_DATA_HOME` "
            "points at, so `opencode` started outside a run lists a person's "
            "own sessions rather than these."
        ),
    )
