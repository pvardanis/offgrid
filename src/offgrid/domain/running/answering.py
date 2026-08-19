"""Holding the model that will answer.

One machine, one pool of memory: what is held is memory the rest of the
machine cannot use, so the model that answers is held alone and goes when the
agent is done with it.

What reaching that state costs is the runtime's business, and each one reaches
it differently. This is where offgrid says which model it wants held.
"""

from dataclasses import replace

from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.runtime import Runtime
from offgrid.shared.exceptions import ModelUnavailableError


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


def hold_model(runtime: Runtime, request: ModelRequest) -> Model:
    """Hold the model that will answer: the one asked for, or the one there.

    Asking for neither a model nor a window is how a run says it wants
    whatever is resident, at whatever it is served at, which costs no load and
    keeps the prompt prefix cached against it.

    Asking for a window and no model asks for the resident model at that
    window. Reading it as "no model named, so nothing to do" would hand back
    the old window while whoever typed the number believes they changed it.

    :param runtime: The runtime to ask.
    :param request: The model a run asked for, and the window to hold it at.

    :return: The model that will answer, stating the window the runtime serves
        it at as well as its ceiling.

    :raise ModelUnavailableError: When the runtime does not have it, or when
        none was named and it is holding nothing.
    :raise ModelNotHeldError: When it took the load and is not holding it.
    :raise RuntimeUnreachableError: When the runtime cannot be reached, when
        the load fails, or when what is already held will not go and this one
        would be loaded on top of it.
    """
    if request.identifier is None and request.context_window is None:
        return get_resident_model(runtime)

    # The port is owed a name, so a run that gave none is answered with the
    # resident model's before anything is asked of the runtime.
    if request.identifier is None:
        request = replace(request, identifier=get_resident_model(runtime).identifier)

    return runtime.ensure_only(request)
