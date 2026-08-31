"""What a published list says this machine can hold."""

from functools import partial
from pathlib import Path

from offgrid.cli.binding import read_profile, there_is_no_profile
from offgrid.cli.reporting import reporting
from offgrid.cli.setup import DEFAULT_RUNTIME
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.running.runtime import RuntimeName
from offgrid.domain.sizing.machine import detect
from offgrid.domain.sizing.reading import get_reading
from offgrid.domain.sizing.recommendation import summarize_findings
from offgrid.leaderboards import LEADERBOARDS
from offgrid.runtimes import describe_model_download
from offgrid.shared.say import tell


def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with reporting():
        runtime_name = _get_runtime_name()
        reading = get_reading(LEADERBOARDS, _cache())

    for line in reading.caveats:
        tell(line)

    say_how = partial(describe_model_download, runtime_name)

    for line in summarize_findings(reading.table, machine, say_how):
        tell(line)


def _get_runtime_name() -> RuntimeName:
    """Name the runtime a model would be downloaded into.

    A name rather than a connection: how a model is downloaded is a fact about
    a runtime, and nothing here is asked of the machine. So a runtime that is
    not running, and a machine that has never run `setup`, are both told the
    same thing.

    A profile that is there and will not load is a different matter, and is
    refused the way every other command refuses it: it names a runtime, and
    guessing past what it says would answer about an adapter its owner did not
    choose.

    :return: The runtime the profile names, or the one `setup` would write
        where there is no profile.

    :raise ProfileError: When there is a profile and it is not one.
    """
    if there_is_no_profile(DEFAULT_PATH):
        return DEFAULT_RUNTIME

    return read_profile(DEFAULT_PATH).runtime.name


def _cache() -> Path:
    """Where the last table read is kept, beside the profile.

    :return: The path to it.
    """
    return DEFAULT_PATH.parent / "leaderboard.json"
