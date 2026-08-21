"""What can be read before a run costs a load."""

from offgrid.cli.binding import bind_run
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH, Profile
from offgrid.domain.running.agent import Agent
from offgrid.domain.running.answering import get_resident_model
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.model import Model
from offgrid.shared.say import tell


def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    # Everything is read before anything is said, so a fault in any of it is
    # reported as offgrid's own error rather than as a traceback under four
    # lines that already looked like an answer.
    profile, model, report, agent = _read_what_can_be_read()

    for line in _describe_what_was_read(profile, model, report, agent):
        tell(line)


@reporting()
def _read_what_can_be_read() -> tuple[Profile, Model, HostedToolsReport, Agent]:
    """Ask the profile, the runtime and the agent what each of them says.

    :return: What was written down, the model that would answer, what the
        agent says it can reach, and the agent itself.
    """
    profile, runtime, agent = bind_run(DEFAULT_PATH)

    model = get_resident_model(runtime)

    return profile, model, agent.read_hosted_tools(), agent


def _describe_what_was_read(
    profile: Profile, model: Model, report: HostedToolsReport, agent: Agent
) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    A value rather than a run of statements that each print, so what the
    report says is settled in one place and said in another.

    :param profile: What was written down.
    :param model: The model that would answer.
    :param report: What the agent says it can reach.
    :param agent: The agent that would be started.

    :return: The lines to say, in the order they are read.
    """
    said = (
        f"runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable",
        f"model     {model.identifier}",
        f"ceiling   {model.context_ceiling or 'unstated'}",
        f"window    {model.context_window or 'unstated'}",
        f"profile   {describe_what_is_asked_for(profile.model)}",
        f"agent     {profile.agent.name.value}, speaking {agent.dialect.value}",
        f"floor     {agent.context_floor}",
        f"hosted    {report.status}",
    )

    # What a run would refuse with, said here instead of after the load it
    # was run to save. Nothing to act on where nothing can be reached.
    if report.status is HostedToolsStatus.DENIED:
        return said

    return (*said, f"          {report.detail} {report.remedy}".rstrip())
