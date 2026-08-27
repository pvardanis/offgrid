"""What offgrid needs of a runtime, and which ones there are.

An adapter binds its own settings once and answers with something satisfying
``Runtime``. Two of its members are attributes, settled when the connection
opens; four are methods, which reach the server.

Why it is shaped this way, and why the attributes are properties, is in
`docs/architecture.md` under "The runtime seam".
"""

from abc import abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, computed_field

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.model import Model, ModelRequest


class RuntimeName(Enum):
    """A runtime offgrid has an adapter for.

    What a profile may name. The registry in ``runtimes/`` binds each of these
    to the adapter that answers for it.
    """

    LMSTUDIO = "lmstudio"


class RuntimeConfig(BaseModel):
    """What one runtime adapter is built from.

    Abstract, and each adapter declares its own. Which one a profile gets is
    the registry's answer to the name it holds, so ``name`` is a property of
    the class rather than a field a file sets.

    Keys it does not name are refused, so a typo under ``runtime:`` is
    reported rather than dropped.

    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``. It
        sits here rather than beside the profile's other keys because it means
        nothing to anything but the runtime.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str

    @computed_field
    @property
    @abstractmethod
    def name(self) -> RuntimeName:
        """Which runtime this is the config for.

        Computed, so that it survives a round trip through the profile: what
        is written is what picks this class again when the file is read.

        :return: The name a profile calls this adapter by.
        """


class Runtime(Protocol):
    """A connection to a runtime holding models on this machine."""

    @property
    def dialects(self) -> frozenset[Dialect]:
        """Every API shape the runtime serves, which pairing is tested against.

        :return: What an agent may speak to talk to it. Never empty, which
            the conformance suite holds every adapter to.
        """
        ...

    @property
    def capabilities(self) -> Capabilities:
        """What this connection can be asked to do.

        :return: What was settled when it opened.
        """
        ...

    def read_catalogue(self) -> list[Model]:
        """List every model the runtime has, held or not.

        :return: The models it can be asked for.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        ...

    def read_held(self) -> list[Model]:
        """List the models the runtime has in memory.

        In a stable order, and the first of them is the model offgrid names as
        the one that would answer. A runtime that answers in the order of a
        set names a different model between two calls with nothing changed.

        :return: What is held, each stating its window and its ceiling.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        ...

    def ensure_only(self, model_request: ModelRequest) -> Model:
        """Hold the model a run asked for, and let go of what else is held.

        An intent rather than a mechanism: one machine has one pool of memory,
        and what reaching that state costs differs enough between runtimes
        that it cannot be orchestrated from outside. The window is part of
        that intent, because holding a model at a size is holding it with one
        more fact in it. A model already held at the window asked for is left
        alone, and one held at a different window is let go of and loaded
        again; one copy is held either way.

        What it promises is the named model held, not an empty pool beside it.
        A model that will not go is said out loud rather than raised where the
        named one is already in memory: there is no load to refuse, and a
        warm model is not worth failing a run over. Where a load *would* be
        needed, it is refused rather than paid into a pool that is still full.

        How long the state lasts is `capabilities` business: a runtime that
        manages its own memory can undo it a second after this returns.

        :param model_request: The model that will answer, and the window to hold
            it at. Its identifier is settled by the time it reaches here: a
            run that named none has already been answered with the resident
            model's own.

        :return: The model as the runtime now serves it, stating the window it
            was loaded with as well as its ceiling.

        :raise ModelUnavailableError: When the runtime does not have it.
        :raise ModelNotHeldError: When it took the model and is not holding it.
        :raise RuntimeUnreachableError: When it cannot be reached, or when a
            load would be needed and what is held will not go.
        """
        ...

    def let_go(self, identifier: str) -> bool:
        """Let go of one model by name.

        The end of a run is a different question from the start of one: a run
        owes a release whatever happened, and that is one model by name rather
        than an intent about the whole pool.

        By name means all of it. A runtime that can hold a model more than
        once owes every copy, because memory left behind is memory the rest of
        the machine cannot use for the session.

        It answers rather than raises, and an adapter owes that: both callers
        are cleanup — a `finally` at the end of a run, and the release after a
        load that failed — so anything raised here replaces the outcome the
        caller was about to report with the failure of tidying up after it.

        :param identifier: The model to let go of.

        :return: Whether the memory came back. ``False`` is said at warning by
            whoever found out, not raised.
        """
        ...


Connect = Callable[[RuntimeConfig], Runtime]
