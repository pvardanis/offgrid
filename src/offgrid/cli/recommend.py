"""What a published list says this machine can hold."""

from pathlib import Path

from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.sizing.machine import detect
from offgrid.domain.sizing.reading import Reading, get_reading
from offgrid.domain.sizing.recommendation import summarize_findings
from offgrid.leaderboards import LEADERBOARDS
from offgrid.shared.say import tell


def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()
    reading = _read_a_published_list()

    for line in reading.caveats:
        tell(line)

    for line in summarize_findings(reading.table, machine):
        tell(line)


@reporting()
def _read_a_published_list() -> Reading:
    """Read the first published list that answers, or the last one that did.

    :return: The table to recommend from, and what to say about where it came
        from.
    """
    return get_reading(LEADERBOARDS, _cache())


def _cache() -> Path:
    """Where the last table read is kept, beside the profile.

    :return: The path to it.
    """
    return DEFAULT_PATH.parent / "leaderboard.json"
