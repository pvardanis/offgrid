"""What an agent can reach that offgrid cannot run, and whether that stops a run.

An agent states what it found; offgrid decides what to do about it. The split
is what lets `run` refuse and `doctor` report the same fact.
"""

from dataclasses import dataclass
from enum import StrEnum, auto

from offgrid.exceptions import HostedToolReachableError


class HostedTools(StrEnum):
    """What an agent can reach that offgrid cannot run on this machine.

    A hosted tool runs on its vendor's servers. Against a model held here
    there is nothing to run it, so the model emits the call as prose and the
    agent returns that as a result — an invented answer, with no error
    anywhere. These are the four answers an adapter can give about that.

    `NONE_OFFERED` — the agent has no such tool. Not an absence of checking:
    a measured fact about that agent at a stated version, recorded with the
    evidence beside it.

    `DENIED` — the agent has one and its configuration refuses it. What a
    healthy machine reports.

    `PERMITTED` — the agent has one and nothing stops it being reached. The
    configuration may say so outright, or an argument may stop the
    configuration being read at all; both leave the tool reachable, and
    differ only in what they say to do about it.

    `UNWRITTEN` — the agent has one and there is no configuration yet to
    speak either way: a machine that has run `offgrid setup` and never
    `offgrid run`. Nothing is wrong, and nothing has been written.

    A `StrEnum` so that a reading prints into a line of `doctor` without
    reaching for `.value`, which `Dialect` and `AgentName` have no call to do:
    they are keys in a profile, and these are read off a report.
    """

    NONE_OFFERED = auto()
    DENIED = auto()
    PERMITTED = auto()
    UNWRITTEN = auto()


@dataclass(frozen=True)
class HostedToolsReport:
    """What an agent said about the tools offgrid cannot run for it.

    The answer is offgrid's to act on; the words are the agent's, because
    only the adapter knows which file to name or which argument to drop.

    :param hosted_tools: Whether one can be reached.
    :param detail: What the adapter found, in its own terms.
    :param remedy: What to change, named the way that agent names it.
    """

    hosted_tools: HostedTools
    detail: str
    remedy: str = ""


def require_hosted_tools_denied(report: HostedToolsReport) -> None:
    """Refuse a run that could reach a tool with nothing here to run it.

    The decision is the same for every agent, because a guarantee that held
    for one agent and not another would tell a person nothing. Only the
    wording is the adapter's.

    :param report: What the agent said about what it can reach.

    :raise HostedToolReachableError: When nothing denies one.
    """
    if report.hosted_tools in (HostedTools.NONE_OFFERED, HostedTools.DENIED):
        return

    raise HostedToolReachableError(f"{report.detail} {report.remedy}".strip())
