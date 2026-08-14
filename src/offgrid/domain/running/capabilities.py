"""What a runtime can be asked to do, as one connection to it found it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    """What a runtime can be asked to do, as this connection found it.

    Each one changes what offgrid does rather than what it reports.

    :param counts_tokens: Whether the runtime will count a prompt's tokens.
        Where it will not, the agent counts them by asking the model, which on
        this machine spends the one model being held.
    :param release_can_be_commanded: Whether a model can be let go of on
        request. Where it cannot, ``ensure_only`` cannot promise what its name
        says.
    :param manages_its_own_memory: Whether the runtime evicts models against a
        ceiling of its own, which can undo that promise a second after it is
        made.
    """

    counts_tokens: bool
    release_can_be_commanded: bool
    manages_its_own_memory: bool
