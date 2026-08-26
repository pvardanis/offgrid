"""What a run could send off this machine, and whether that stops it.

An agent states what it found; offgrid decides what to do about it, which is
what lets `run` refuse and `doctor` report the same fact.

There is more than one way off the machine and they are not one answer. A tool
that runs on a vendor's servers and a published transcript fail differently and
are fixed differently, so an adapter answers about each in turn — one reading
per subject — rather than folding them into a status that cannot say which.

An adapter answering about fewer subjects than there are satisfies the type
checker, so the guard counts them: a reading nobody gave is refused before any
is read. `tests/test_agent_leaving.py` asks every adapter the same thing, which
is where an adapter finds out; this keeps it true of a run, not just the suite.
"""

from dataclasses import dataclass
from enum import StrEnum, auto

from offgrid.shared.exceptions import CouldLeaveThisMachineError


class Subject(StrEnum):
    """One way a run could reach off this machine.

    A `StrEnum` carrying the words a person reads, because these print into a
    line of `doctor` beside the status: one reading is one line, and the line
    says which of them it is about.
    """

    HOSTED_TOOLS = "hosted tools"
    TRANSCRIPT_SHARING = "transcript sharing"


class Status(StrEnum):
    """What an agent found about one of those, in this configuration.

    `NONE_OFFERED` — the agent has no such thing at all. Not an absence of
    checking: a measured fact about a stated version, with the evidence beside
    it. `DENIED` — it has one and what it will load refuses it. `PERMITTED` —
    it has one and nothing stops it, whether the configuration says so, an
    argument stops it being read, or an argument asks for it. `UNWRITTEN` — it
    has one and nothing says either way.

    Two configurations reach `UNWRITTEN` and are fixed differently — one
    `configure` writes on its way past, one only a person can finish — so the
    remedy travels on the reading rather than off the status.
    """

    NONE_OFFERED = auto()
    DENIED = auto()
    PERMITTED = auto()
    UNWRITTEN = auto()


@dataclass(frozen=True)
class Reading:
    """What an agent said about one way off this machine.

    The answer is offgrid's to act on; the words are the agent's, because
    only the adapter knows which file to name or which argument to drop.

    :param subject: Which way off the machine this is about.
    :param status: Whether it can be reached.
    :param detail: What the adapter found, in its own terms.
    :param remedy: What to change, named the way that agent names it. Empty
        only where the reading settles nothing needing a change.
    """

    subject: Subject
    status: Status
    detail: str
    remedy: str = ""

    def __post_init__(self) -> None:
        """Refuse a reading a person could not act on, where it stops a run.

        A refusal with no remedy is a wall with no door, and the empty default
        above makes leaving one out the easy mistake.

        :raise ValueError: When the detail is empty, or a reading that stops a
            run says nothing to do about it.
        """
        if not self.detail.strip():
            raise ValueError(
                f"A reading about {self.subject} says nothing it found, and "
                "every status is a claim `doctor` prints the evidence for."
            )

        if not self.stays_here and not self.remedy.strip():
            raise ValueError(
                f"A reading about {self.subject} is {self.status} and names "
                "nothing to change, so a run refuses on it saying nothing to do."
            )

    @property
    def stays_here(self) -> bool:
        """Whether this reading leaves nothing able to reach off the machine.

        :return: True where the agent has no such thing or refuses it.
        """
        return self.status in (Status.NONE_OFFERED, Status.DENIED)

    @property
    def said(self) -> str:
        """What the adapter found and what to do about it, as one sentence.

        One join for the refusal and the report, so neither can come to
        disagree with the other about the gap an empty remedy leaves.

        :return: The detail, and the remedy where there is one.
        """
        return f"{self.detail} {self.remedy}".strip()


def require_nothing_leaves(readings: tuple[Reading, ...]) -> None:
    """Refuse a run that could send something off this machine.

    The decision is the same for every agent, because a guarantee that held for
    one agent and not another would tell a person nothing. It refuses with the
    first unsettled reading in `Subject` order, so a person gets one thing to
    fix rather than a list, and the same one each run until they have. A
    subject nobody answered is refused before any is read.

    :param readings: What the agent said about each way off this machine.

    :raise CouldLeaveThisMachineError: When any of them is not settled.
    :raise ValueError: When they do not answer every subject exactly once,
        which is an adapter being wrong rather than a machine.
    """
    answered = [reading.subject for reading in readings]

    if sorted(answered) != sorted(Subject):
        raise ValueError(
            f"The agent answered about {[str(s) for s in answered]}, and a run "
            f"is asked about {[str(s) for s in Subject]}, once each. An adapter "
            "with no such thing answers `NONE_OFFERED` and the evidence for it."
        )

    # Reached by subject because the tuple's own order is the adapter's: two
    # adapters answering the same pair in a different order would send two
    # people to different files for the same machine.
    by_subject = {reading.subject: reading for reading in readings}

    for subject in Subject:
        reading = by_subject[subject]

        if not reading.stays_here:
            raise CouldLeaveThisMachineError(f"{subject}: {reading.said}")
