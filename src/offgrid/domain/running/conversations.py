"""Where an agent keeps what it wrote down of a session, and the way back in.

A run is its own installation, so a conversation it started is one an agent
started by hand does not find: what each of them reads is a directory offgrid
points it at, and only a run points it there. `docs/decisions.md` says why that
partition is worth having, and holds the measurement behind it, under "A
conversation started here is resumed here".

Its own value rather than a subject in `leaving.py`, because nothing here left
the machine. Every subject there is about a run sending something out, and a
directory is none of what `Status` offers: not `DENIED`, `PERMITTED` or
`UNWRITTEN`, and `NONE_OFFERED` would say the agent keeps no conversations at
all. A fifth status used by one subject would say the two are the same question.
"""

from dataclasses import dataclass
from pathlib import Path

STARTED_ON_ITS_OWN = (
    "An agent started outside a run reads the directory it keeps its own "
    "conversations in, which is not this one, so none of these are in what it "
    "offers."
)
"""What is true of every adapter, said once so no adapter can drop it.

Offgrid's own doing rather than a claim about a vendor: a run points the agent
at this directory and nothing else does, so an agent started by hand reads what
it reads by default. What that costs — which command finds nothing, and against
which version it was measured — is the adapter's, and travels in `resumed_by`.
"""


@dataclass(frozen=True)
class Conversations:
    """Where one agent keeps the conversations a run started, and the way back.

    Both halves are the adapter's, because only it knows which directory it
    writes into and which argument opens one again.

    What it does not promise is that the directory is one of offgrid's. That is
    the whole point of the member and it cannot be checked here — the home is
    bound at import and a domain value has no business reading it — so
    `tests/test_agent_conversations.py` asks it of every adapter instead,
    against the home a run actually uses.

    :param kept_in: The directory offgrid points the agent at, which is where
        what a run wrote down lands. What sits under it is the agent's own
        layout rather than anything offgrid settles.
    :param resumed_by: How to open one of them again, named the way that agent
        names it.
    """

    kept_in: Path
    resumed_by: str

    def __post_init__(self) -> None:
        """Refuse an answer a person could not act on.

        :raise ValueError: When the directory is relative, or nothing says how
            to get back into a conversation kept there.
        """
        if not self.kept_in.is_absolute():
            raise ValueError(
                f"Conversations are said to be kept at {self.kept_in}, which is "
                "relative, so where it points depends on where the person "
                "reading the report is standing."
            )

        if not self.resumed_by.strip():
            raise ValueError(
                f"Conversations are said to be kept at {self.kept_in} and nothing "
                "names the command that opens one, so a person is told where to "
                "look and not how to get back in."
            )

    @property
    def said(self) -> str:
        """The way back in, and what an agent started by hand reads instead.

        One join for every report, the way `Reading.said` is one join for the
        refusal and the report: the second half is the finding rather than the
        remedy, and an adapter that had to repeat it is one that can drop it.

        :return: What to type, and why nothing else finds these.
        """
        return f"{self.resumed_by} {STARTED_ON_ITS_OWN}"
