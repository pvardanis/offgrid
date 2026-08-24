"""What a run can be told before it costs a load, and how it reads."""

from dataclasses import dataclass

from offgrid.domain.profile import Profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.wording import describe_what_was_stated

HELD_NOTHING = "model     nothing held"


@dataclass(frozen=True)
class Checkup:
    """Everything `doctor` read, including what it found nothing to read.

    Readings rather than the things that answered them: the agent port can
    write its own settings, and a value the report is built from has no call
    to carry the means of doing it.

    :param profile: What was written down.
    :param resident: The model the runtime is holding, or ``None`` where it
        holds none — which the rest of the report survives, because a runtime
        holding nothing still answered.
    :param hosted_tools: What the agent says it can reach.
    :param dialect: What the agent speaks.
    :param served: Every dialect the runtime serves, which says whether an
        agent other than this one would pair with it.
    :param context_floor: The smallest window the agent can start in.
    :param discarded: Every window this runtime discarded for the model it is
        holding, and empty where it discarded none and where the records could
        not be read — which is itself a finding, carried in `unreadable`.
    :param unreadable: Why the records could not be read, where they could not.
        A stale file nobody has heard of is worth a line, not the whole report.
    """

    profile: Profile
    resident: Model | None
    hosted_tools: HostedToolsReport
    dialect: Dialect
    served: frozenset[Dialect]
    context_floor: int
    discarded: tuple[DiscardedWindow, ...]
    unreadable: str | None


def describe_what_was_read(checkup: Checkup) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    A value rather than a run of statements that each print, so what the
    report says is settled in one place and said in another.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The lines to say, in the order they are read.
    """
    profile, hosted_tools = checkup.profile, checkup.hosted_tools

    said = (
        f"runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable",
        f"serving   {', '.join(sorted(d.value for d in checkup.served))}",
        *_describe_the_model(checkup.resident, profile.model),
        f"profile   {describe_what_is_asked_for(profile.model)}",
        f"agent     {profile.agent.name.value}, speaking {checkup.dialect.value}",
        f"floor     {checkup.context_floor}",
        f"hosted    {hosted_tools.status}",
    )

    said = (*said, *_describe_a_discarded_window(checkup))

    # What a run would refuse with, said here instead of after the load it
    # was run to save. Nothing to act on where nothing can be reached.
    if hosted_tools.status is HostedToolsStatus.DENIED:
        return said

    return (*said, f"          {hosted_tools.detail} {hosted_tools.remedy}".rstrip())


def _describe_the_model(model: Model | None, request: ModelRequest) -> tuple[str, ...]:
    """Say which model would answer, and at what, or that none would.

    A runtime holding nothing keeps its lines in the column, the two numbers
    marked `unknown` rather than left out: a number about a model that is not
    held is unknown, where `unstated` is what a held model states when the
    runtime says no number for it.

    :param model: The model the runtime is holding, or ``None`` for none.
    :param request: What the profile asks the next run for, which decides
        whether a runtime holding nothing needs a hand.

    :return: The model's lines, and what to do about a runtime holding
        nothing where the profile names none either.
    """
    if model is not None:
        return (
            f"model     {model.identifier}",
            f"ceiling   {describe_what_was_stated(model.context_ceiling)}",
            f"window    {describe_what_was_stated(model.context_window)}",
        )

    unknown = ("ceiling   unknown", "window    unknown")

    # `settle_what_to_run` folds the profile's identifier in beside `--model`,
    # and `hold_model` reaches for the resident model only where the pair of
    # them named none. So a profile naming one needs nothing held, and saying
    # otherwise sends someone to load a model for a run that would load it.
    if request.identifier is not None:
        return (HELD_NOTHING, *unknown)

    # Under the line it is about, where the hosted reading puts its own.
    return (
        HELD_NOTHING,
        "          Load a model in the runtime, or name one under `model:` "
        "in the profile.",
        *unknown,
    )


def _describe_a_discarded_window(checkup: Checkup) -> tuple[str, ...]:
    """Say that offgrid stopped asking for a window, and how to make it ask.

    Deleting the file makes offgrid ask again, so this is where it is named:
    `doctor` is what a person runs when something is not what they asked for.
    The number the runtime served then is said as what it was — what it serves
    now is the `window` line above, and the two are read together.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: A line for each window discarded and the way back under them, and
        nothing where none was.
    """
    if checkup.unreadable is not None:
        return (f"discarded {checkup.unreadable}",)

    if not checkup.discarded:
        return ()

    return (
        *(
            f"discarded {record.asked_for} was asked for on {record.dated} "
            f"and {record.served} served then, so offgrid is not asking again."
            for record in checkup.discarded
        ),
        f"Delete {discarded_windows.DEFAULT_PATH} to ask again.",
    )
