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
which version it was measured — is the adapter's, and travels in `measured`.
"""


@dataclass(frozen=True)
class Conversations:
    """Where one agent keeps the conversations a run started, and the way back.

    Every half is the adapter's, because only it knows which directory it writes
    into, which argument opens one again, and against which version that was
    measured.

    The way back is split from the provenance so each is read where it belongs:
    the commands are what a person acts on, shown wherever the way back is; the
    provenance is a diagnostic `doctor` carries and a compact surface leaves
    out. `said` joins them the one way the report reads them.

    What it does not promise is that the directory is one of offgrid's. That is
    the whole point of the member and it cannot be checked here — the home is
    bound at import and a domain value has no business reading it — so
    `tests/test_agent_conversations.py` asks it of every adapter instead,
    against the home a run actually uses.

    :param kept_in: The directory offgrid points the agent at, which is where
        what a run wrote down lands. What sits under it is the agent's own
        layout rather than anything offgrid settles.
    :param resume_with: The command or commands that open one of them again,
        named the way that agent names them.
    :param measured: Against which version the way back was measured, and any
        finding that came with it — the adapter's provenance, which `doctor`
        prints and a compact surface leaves out. Empty where there is none.
    """

    kept_in: Path
    resume_with: str
    measured: str = ""

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

        if not self.resume_with.strip():
            raise ValueError(
                f"Conversations are said to be kept at {self.kept_in} and nothing "
                "names the command that opens one, so a person is told where to "
                "look and not how to get back in."
            )

    @property
    def said(self) -> str:
        """The way back in, its provenance, and what an agent by hand reads.

        One join for every report, the way `Reading.said` is one join for the
        refusal and the report: the commands, then the provenance where there
        is any, then the finding that a run's conversations are nowhere the
        agent looks on its own.

        :return: What to type, against what it was measured, and why nothing
            else finds these.
        """
        if self.measured:
            way_back = f"{self.resume_with}, {self.measured}"
        else:
            way_back = self.resume_with

        return f"{way_back} {STARTED_ON_ITS_OWN}"
