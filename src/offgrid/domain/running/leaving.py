"""What a run could send off this machine, and whether that stops it.

An agent states what it found; offgrid decides what to do about it. The split
is what lets `run` refuse and `doctor` report the same fact.

There is more than one way off the machine and they are not one answer. A tool
that runs on a vendor's servers and a transcript published to one fail
differently and are fixed differently, so an adapter answers about each in
turn — one reading per subject — rather than folding them into a status that
cannot say which of them a refusal was about.

That every adapter answers about every subject is stated in
`tests/test_agent_leaving.py` rather than guarded here: an adapter that answers
about nothing satisfies this module and the type checker both, and only a suite
asking every adapter for every subject sees it.
"""

from dataclasses import dataclass
from enum import StrEnum, auto

from offgrid.shared.exceptions import CouldLeaveThisMachineError


class Subject(StrEnum):
    """One way a run could reach off this machine.

    A `StrEnum` carrying the words a person reads, because these print into a
    line of `doctor` beside the status: one reading is one line, and the line
    has to say which of them it is about.
    """

    HOSTED_TOOLS = "hosted tools"
    TRANSCRIPT_SHARING = "transcript sharing"


class Status(StrEnum):
    """What an agent found about one of those, in this configuration.

    A hosted tool runs on its vendor's servers. Against a model held here
    there is nothing to run it, so the model emits the call as prose and the
    agent returns that as a result — an invented answer, with no error
    anywhere. A published transcript is the other failure: the run works
    exactly as asked and the reading leaves the machine anyway, which is the
    promise `docs/decisions.md` makes. These are the four answers an adapter
    can give about either.

    `NONE_OFFERED` — the agent has no such thing at all. Not an absence of
    checking: a measured fact about that agent at a stated version, recorded
    with the evidence beside it.

    `DENIED` — the agent has one and what it will load refuses it. What a
    healthy machine reports.

    `PERMITTED` — the agent has one and nothing stops it. The configuration
    may say so outright, or an argument may stop the configuration being read
    at all, or an argument may ask for it directly; all of them leave it
    reachable, and differ only in what they say to do about it.

    `UNWRITTEN` — the agent has one and nothing it will load says either way.
    Two configurations reach this and they are fixed differently, which is why
    the remedy travels on the reading rather than being read off the status: a
    file holding nothing is one `configure` writes on its way past, and a file
    holding an edit that never mentions the setting is one only a person can
    finish, since `configure` will not write into an edit.

    A `StrEnum` so that a reading prints into a line of `doctor` without
    reaching for `.value`, which `Dialect` and `AgentName` have no call to do:
    they are keys in a profile, and these are read off a report.
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
    :param remedy: What to change, named the way that agent names it.
    """

    subject: Subject
    status: Status
    detail: str
    remedy: str = ""

    @property
    def stays_here(self) -> bool:
        """Whether this reading leaves nothing able to reach off the machine.

        :return: True where the agent has no such thing or refuses it.
        """
        return self.status in (Status.NONE_OFFERED, Status.DENIED)


def require_nothing_leaves(readings: tuple[Reading, ...]) -> None:
    """Refuse a run that could send something off this machine.

    The decision is the same for every agent, because a guarantee that held
    for one agent and not another would tell a person nothing. Only the
    wording is the adapter's.

    The first reading that is not settled is what it refuses with, so a person
    is given one thing to fix rather than a list to read: the run is made again
    once they have, and the next reading answers then.

    :param readings: What the agent said about each way off this machine.

    :raise CouldLeaveThisMachineError: When any of them is not settled.
    """
    for reading in readings:
        if reading.stays_here:
            continue

        raise CouldLeaveThisMachineError(
            f"{reading.subject}: {reading.detail} {reading.remedy}".strip()
        )
