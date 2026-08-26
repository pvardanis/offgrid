"""Where an agent keeps what it wrote down of a session, and the way back in.

A run is its own installation, so a conversation it started is one nothing
outside a run finds: `claude --resume <id>` in an ordinary terminal answers "No
conversation found with session ID" for a session offgrid started minutes
earlier. `docs/decisions.md` says why that partition is worth having, under "A
conversation started here is resumed here".

Its own value rather than a subject in `leaving.py`, because nothing here left
the machine. Every subject there is about a run sending something out, and a
directory is not `DENIED`, `PERMITTED` or `UNWRITTEN`; a fifth status used by
one subject would say the two are the same question.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Conversations:
    """Where one agent keeps the conversations a run started, and the way back.

    Both halves are the adapter's, because only it knows which directory it
    writes into and which argument opens one again.

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
                "says how to open one, which is a directory a person already had."
            )
