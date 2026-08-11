"""What offgrid needs of a runtime, and which ones there are.

A runtime adapter is a module exposing one factory. The factory binds an
address once and answers with something satisfying ``Runtime``, so an address
appears in one signature rather than in five and a connection has somewhere to
keep what it needs.

Two of the members are attributes and four are methods, and the split says
which is which: an attribute settles when the connection opens, so reading it
is free and cannot fail, while a method reaches the server, costs time, and
can raise.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from offgrid.dialect import Dialect
from offgrid.model import Model


class RuntimeName(Enum):
    """A runtime offgrid has an adapter for.

    What a profile may name. The registry in ``runtimes/`` binds each of these
    to the adapter that answers for it.
    """

    LMSTUDIO = "lmstudio"


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


class Runtime(Protocol):
    """A connection to a runtime holding models on this machine.

    :param dialect: The API shape it serves.
    :param capabilities: What it can be asked to do.
    """

    dialect: Dialect
    capabilities: Capabilities

    def read_catalogue(self) -> list[Model]:
        """List every model the runtime has, held or not.

        :return: The models it can be asked for.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        ...

    def read_held(self) -> list[Model]:
        """List the models the runtime has in memory.

        :return: What is held, described by the context each is served at.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        ...

    def ensure_only(self, identifier: str) -> Model:
        """Hold the named model and nothing else.

        An intent rather than a mechanism: one machine has one pool of memory,
        and what reaching that state costs differs enough between runtimes
        that it cannot be orchestrated from outside.

        :param identifier: The model that will answer.

        :return: The model as the runtime now serves it, which is the window
            it was loaded with rather than its ceiling.

        :raise ModelUnavailableError: When the runtime does not have it.
        :raise ModelNotHeldError: When it took the model and is not holding it.
        :raise RuntimeUnreachableError: When it cannot be reached, or when what
            is already held will not go.
        """
        ...

    def let_go(self, identifier: str) -> bool:
        """Let go of one model by name.

        The end of a run is a different question from the start of one: a run
        owes a release whatever happened, and that is one model by name rather
        than an intent about the whole pool.

        :param identifier: The model to let go of.

        :return: Whether the memory came back.
        """
        ...


Connect = Callable[[str], Runtime]
