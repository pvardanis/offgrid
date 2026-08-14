"""What offgrid needs of a runtime, and which ones there are.

An adapter binds its own settings once and answers with something satisfying
``Runtime``. Two of its members are attributes, settled when the connection
opens; four are methods, which reach the server.

Why it is shaped this way, and why the attributes are properties, is in
`docs/architecture.md` under "The runtime seam".
"""

from collections.abc import Callable
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from offgrid.capabilities import Capabilities
from offgrid.dialect import Dialect
from offgrid.model import Model


class RuntimeName(Enum):
    """A runtime offgrid has an adapter for.

    What a profile may name. The registry in ``runtimes/`` binds each of these
    to the adapter that answers for it.
    """

    LMSTUDIO = "lmstudio"


class RuntimeConfig(BaseModel):
    """The profile's runtime section, as much of it as offgrid itself reads.

    Extra keys are carried rather than refused, because the section belongs to
    whichever adapter the name picks and this type cannot know what that one
    reads. The registry narrows it to that adapter's own config, which forbids
    what it does not name.

    :param name: Which runtime adapter to use.
    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``. It
        sits here rather than beside the profile's other keys because it means
        nothing to anything but the runtime.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    name: RuntimeName = RuntimeName.LMSTUDIO
    host: str


class Runtime(Protocol):
    """A connection to a runtime holding models on this machine."""

    @property
    def dialect(self) -> Dialect:
        """The API shape the runtime serves.

        :return: The dialect an agent has to speak to talk to it.
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

        :return: What is held, described by the context each is served at.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        ...

    def ensure_only(self, identifier: str) -> Model:
        """Hold the named model, and let go of what else is held.

        An intent rather than a mechanism: one machine has one pool of memory,
        and what reaching that state costs differs enough between runtimes
        that it cannot be orchestrated from outside.

        What it promises is the named model held, not an empty pool beside it.
        A model that will not go is said out loud rather than raised where the
        named one is already in memory: there is no load to refuse, and a
        warm model is not worth failing a run over. Where a load *would* be
        needed, it is refused rather than paid into a pool that is still full.

        How long the state lasts is `capabilities` business: a runtime that
        manages its own memory can undo it a second after this returns.

        :param identifier: The model that will answer.

        :return: The model as the runtime now serves it, which is the window
            it was loaded with rather than its ceiling.

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

MakeRuntimeConfig = Callable[[RuntimeConfig], RuntimeConfig]
"""Turn the profile's runtime section into one adapter's own settings.

It takes the section and nothing else: where the runtime listens is the one
thing every runtime needs, and the section already says it. It raises
``ProfileError`` where the section says something that adapter cannot read.
"""
