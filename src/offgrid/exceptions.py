"""Errors raised by offgrid, each naming what to do next."""


class OffgridError(Exception):
    """Base class for every error offgrid raises deliberately."""


class UnsupportedMachineError(OffgridError):
    """The host is not an Apple Silicon Mac."""


class RuntimeUnreachableError(OffgridError):
    """The model server did not answer."""


class ModelUnavailableError(OffgridError):
    """The requested model is not present on the runtime."""


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


class ProfileError(OffgridError):
    """The stored profile is missing, unreadable, or fails validation."""
