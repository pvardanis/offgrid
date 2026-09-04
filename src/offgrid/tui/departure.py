"""What the picker exits with, handed back to whoever opened the screen.

The screen never holds a model itself: it assembles a profile and leaves with
it, and whoever opened it carries out the run. This is the wish it exits with —
the profile assembled, and whether the key that writes was the one pressed.
"""

from dataclasses import dataclass

from offgrid.domain.profile import Profile


@dataclass(frozen=True)
class Departure:
    """What a person assembled, and how they chose to leave the screen with it.

    Handed back to whoever opened the screen, which carries out the run in the
    plain lines a run is read in. The screen never holds a model itself; this
    is the wish it exits with.

    :param profile: What was assembled — runtime, agent and model — as a run is
        made from it.
    :param saved: Whether the key that writes was the one pressed, which is what
        the report of the save is about. A past fact rather than a request: the
        file is already written by the time this is handed back, and this says
        whether to say so.
    """

    profile: Profile
    saved: bool
