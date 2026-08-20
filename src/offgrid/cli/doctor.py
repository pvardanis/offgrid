"""What can be read before a run costs a load."""

from offgrid.binding import bind_run
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.running.answering import get_resident_model
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.hosted_tools import HostedToolsStatus
from offgrid.shared.say import tell


def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    # Reading, binding and both askings happen before anything is printed, so
    # a fault in any of them is reported as offgrid's own error rather than as
    # a traceback under four lines that already looked like an answer.
    with reporting():
        profile, runtime, agent = bind_run(DEFAULT_PATH)

        model = get_resident_model(runtime)
        report = agent.read_hosted_tools()

    tell(
        f"  runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable"
    )
    tell(f"  model     {model.identifier}")
    tell(f"  ceiling   {model.context_ceiling or 'unstated'}")
    tell(f"  window    {model.context_window or 'unstated'}")
    tell(f"  profile   {describe_what_is_asked_for(profile.model)}")
    tell(f"  agent     {profile.agent.name.value}, speaking {agent.dialect.value}")
    tell(f"  floor     {agent.context_floor}")
    tell(f"  hosted    {report.status}")

    # What a run would refuse with, said here instead of after the load it
    # was run to save. Nothing to act on where nothing can be reached.
    if report.status is not HostedToolsStatus.DENIED:
        tell(f"            {report.detail} {report.remedy}".rstrip())
