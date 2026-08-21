"""What can be read before a run costs a load."""

from dataclasses import dataclass

import typer

from offgrid.cli.binding import bind_run
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH, Profile
from offgrid.domain.running.answering import find_resident_model
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.say import tell

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
    :param context_floor: The smallest window the agent can start in.
    """

    profile: Profile
    resident: Model | None
    hosted_tools: HostedToolsReport
    dialect: Dialect
    context_floor: int


def doctor() -> None:
    """Report what the profile, the runtime and the agent each say.

    :raise Exit: With 1 where the runtime is holding no model, which is a
        finding rather than a fault in reaching it, so it is said in the
        report as well.
    """
    # Everything is read before anything is said, so a fault in any of it is
    # reported as offgrid's own error rather than as a traceback under lines
    # that already looked like an answer.
    checkup = _read_what_can_be_read()

    for line in _describe_what_was_read(checkup):
        tell(line)

    # The same code every other fault gets, so that a script does not read a
    # report with no model in it as a run that would work.
    if checkup.resident is None:
        raise typer.Exit(1)


@reporting()
def _read_what_can_be_read() -> Checkup:
    """Ask the profile, the runtime and the agent what each of them says.

    :return: What each of them answered.
    """
    profile, runtime, agent = bind_run(DEFAULT_PATH)

    resident = find_resident_model(runtime)

    return Checkup(
        profile=profile,
        resident=resident,
        hosted_tools=agent.read_hosted_tools(),
        dialect=agent.dialect,
        context_floor=agent.context_floor,
    )


def _describe_what_was_read(checkup: Checkup) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    A value rather than a run of statements that each print, so what the
    report says is settled in one place and said in another.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The lines to say, in the order they are read.
    """
    profile, hosted = checkup.profile, checkup.hosted_tools

    said = (
        f"runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable",
        *_describe_the_model(checkup.resident, profile.model),
        f"profile   {describe_what_is_asked_for(profile.model)}",
        f"agent     {profile.agent.name.value}, speaking {checkup.dialect.value}",
        f"floor     {checkup.context_floor}",
        f"hosted    {hosted.status}",
    )

    # What a run would refuse with, said here instead of after the load it
    # was run to save. Nothing to act on where nothing can be reached.
    if hosted.status is HostedToolsStatus.DENIED:
        return said

    return (*said, f"          {hosted.detail} {hosted.remedy}".rstrip())


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
            f"ceiling   {model.context_ceiling or 'unstated'}",
            f"window    {model.context_window or 'unstated'}",
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
