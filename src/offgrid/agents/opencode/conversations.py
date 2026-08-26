"""Where an OpenCode run leaves the conversation, and how to open it again.

Its own module for the reason the two readings beside it have theirs: nothing
in the file offgrid writes decides this. A session lands in the store the
launch points `XDG_DATA_HOME` at, and that variable is the whole of the answer.
"""

from pathlib import Path

from offgrid.agents.opencode.configuring import DATA_HOME
from offgrid.domain.running.conversations import Conversations

# What `opencode run --help` and `opencode session --help` offer at the version
# below: `-c, --continue` takes up the last session, `-s, --session <id>` takes
# up one by identifier, and `opencode session list` names what is there.
CONTINUE = "--continue"
SESSION = "--session"
LISTING = "session list"
OFFERS_RESUMING = "opencode 1.18.23"

# What was measured on the version below, and no more than it: `session list`
# with `XDG_DATA_HOME` pointed at a directory nothing had written to created the
# store there and answered with nothing, while the same command without the
# variable listed a person's own sessions. So which store is read is settled by
# what points that variable, which a run is one of.
#
# The listing is named with the variable rather than through `offgrid run`,
# because a run holds a model and lets it go again on its way out: looking a
# session up would cost the load the session is being looked up to avoid.
#
# The two resuming flags were not measured, because measuring one means
# generating against whatever it resolves to — the same reason `sharing.py`
# leaves `--share` unmeasured. What would settle it is a session started under a
# run and taken up again by identifier.
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
            f"`offgrid run -- run {CONTINUE}` takes up the last one and "
            f"`offgrid run -- run {SESSION} <id>` one by identifier, measured "
            f"against {OFFERS_RESUMING}. To read what is there without holding "
            f"a model, point `{DATA_HOME}` at it and run `opencode {LISTING}`: "
            f"measured against {MEASURED_AGAINST}, that listing answers out of "
            "the store the variable names."
        ),
    )
