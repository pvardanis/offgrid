"""Errors raised by offgrid, each naming what to do next."""


class OffgridError(Exception):
    """Base class for every error offgrid raises deliberately."""


class UnsupportedMachineError(OffgridError):
    """The host is not an Apple Silicon Mac."""


class RuntimeUnreachableError(OffgridError):
    """The model server did not answer."""


class ModelUnavailableError(OffgridError):
    """The requested model is not present on the runtime."""


class ModelNotHeldError(ModelUnavailableError):
    """The runtime took the model and is not holding it.

    Which is not the same as a runtime that cannot be reached: this one
    answered, twice, and the second answer disagreed with the first.
    """


class LeaderboardUnavailableError(OffgridError):
    """The published list could not be fetched, or held no table.

    Both leave offgrid with nothing to recommend from, and neither says
    anything about this machine.
    """


class LeaderboardUnreachableError(LeaderboardUnavailableError):
    """Nothing answered for the published list.

    Ordinary: a network is the one thing offgrid needs that is not on this
    machine. A run that has read the list before can go on without it.
    """


class LeaderboardUnreadableError(LeaderboardUnavailableError):
    """The published list answered, and what came back held no table.

    Which is the page being rewritten, and is worth saying out loud even
    where a table read earlier saves the answer: a fetch that quietly stops
    parsing is the feature dying without anyone noticing.
    """


class DialectMismatchError(OffgridError):
    """The agent speaks a different API dialect than the runtime serves.

    :param message: What went wrong and what to do about it.
    :param served: The dialect the runtime serves.
    :param expected: The dialect the agent expects.
    """

    def __init__(self, message: str, served: object, expected: object) -> None:
        """Record which dialect each side speaks alongside the message."""
        super().__init__(message)
        self.served = served
        self.expected = expected


class AgentSettingsError(OffgridError):
    """The agent's settings would let it do something offgrid cannot back."""


class ProfileError(OffgridError):
    """The stored profile is missing, unreadable, or fails validation."""
