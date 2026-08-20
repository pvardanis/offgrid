"""What a published list says this machine can hold."""

from pathlib import Path

from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.sizing.machine import detect
from offgrid.domain.sizing.reading import get_reading
from offgrid.domain.sizing.recommendation import summarize_findings
from offgrid.leaderboards import LEADERBOARDS
from offgrid.shared.say import tell


def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with reporting():
        reading = get_reading(LEADERBOARDS, _cache())

    for line in reading.caveats:
        tell(line)

    for line in summarize_findings(reading.table, machine):
        tell(line)


def _cache() -> Path:
    """Where the last table read is kept, beside the profile.

    :return: The path to it.
    """
    return DEFAULT_PATH.parent / "leaderboard.json"
