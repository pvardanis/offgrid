"""Holding the model that will answer.

One machine, one pool of memory: what is held is memory the rest of the
machine cannot use, so the model that answers is held alone and goes when the
agent is done with it.

What reaching that state costs is the runtime's business, and each one reaches
it differently. This is where offgrid says which model it wants held.
"""

from offgrid.exceptions import ModelUnavailableError
from offgrid.model import Model
from offgrid.runtime import Runtime


def get_resident_model(runtime: Runtime) -> Model:
    """Find the model the runtime is already holding.

    :param runtime: The runtime to ask.

    :return: The model that would answer.

    :raise ModelUnavailableError: When the runtime holds none.
    :raise RuntimeUnreachableError: When it cannot be reached.
    """
    in_memory = runtime.read_held()

    if not in_memory:
        raise ModelUnavailableError(
            "The runtime is holding no model. Load a model in it, then try again."
        )

    # A runtime can hold several; which of them answers is decided by the
    # request, and the first in catalogue order is the one offgrid names.
    return in_memory[0]


def hold_model(runtime: Runtime, identifier: str | None) -> Model:
    """Hold the model that will answer: the one named, or the one already there.

    Naming none is how a run says it wants whatever is resident, which costs
    no load and keeps the prompt prefix cached against it.

    :param runtime: The runtime to ask.
    :param identifier: The model asked for, or ``None`` for the resident one.

    :return: The model that will answer, described by the context the runtime
        serves it at.

    :raise ModelUnavailableError: When the runtime does not have it, or when
        none was named and it is holding nothing.
    :raise ModelNotHeldError: When it took the load and is not holding it.
    :raise RuntimeUnreachableError: When the runtime cannot be reached, when
        the load fails, when another model answers, or when what is already
        held will not go and this one would be loaded on top of it.
    """
    if identifier is None:
        return get_resident_model(runtime)

    return runtime.ensure_only(identifier)
