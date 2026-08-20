"""Holding the model that will answer.

One machine, one pool of memory: what is held is memory the rest of the
machine cannot use, so the model that answers is held alone and goes when the
agent is done with it.

What reaching that state costs is the runtime's business, and each one reaches
it differently. This is where offgrid says which model it wants held.
"""

from offgrid.domain.running.context_window import (
    refuse_a_window_above_the_ceiling,
    refuse_a_window_below_the_floor,
)
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


def hold_model(
    runtime: Runtime, model_request: ModelRequest, *, context_floor: int
) -> Model:
    """Hold the model that will answer: the one asked for, or the one there.

    Asking for neither a model nor a window is how a run says it wants
    whatever is resident, at whatever it is served at, which costs no load and
    keeps the prompt prefix cached against it.

    Asking for a window and no model asks for the resident model at that
    window. Reading it as "no model named, so nothing to do" would hand back
    the old window while whoever typed the number believes they changed it.

    A window the agent could not start in and one the model could not honour
    are both refused before anything is loaded, rather than met at the agent's
    own startup or served as a number nothing downstream can question.

    :param runtime: The runtime to ask.
    :param model_request: The model a run asked for, and the window to hold it at.
    :param context_floor: The smallest window the agent can start in.

    :return: The model that will answer, stating the window the runtime serves
        it at as well as its ceiling.

    :raise ContextWindowUnworkableError: When the window asked for is below
        the agent's floor or above the model's ceiling.
    :raise ModelUnavailableError: When the runtime does not have it, or when
        none was named and it is holding nothing.
    :raise ModelNotHeldError: When it took the load and is not holding it.
    :raise RuntimeUnreachableError: When the runtime cannot be reached, when
        the load fails, or when what is already held will not go and this one
        would be loaded on top of it.
    """
    refuse_a_window_below_the_floor(model_request.context_window, floor=context_floor)

    resident = None

    # The port is owed a name, so a run that gave none is answered with the
    # resident model's before the load is asked for.
    if model_request.identifier is None:
        resident = get_resident_model(runtime)

        if model_request.context_window is None:
            return resident

        model_request = model_request.model_copy(
            update={"identifier": resident.identifier}
        )

    refuse_a_window_above_the_ceiling(
        model_request, ceiling=_read_ceiling(runtime, model_request, resident)
    )

    return runtime.ensure_only(model_request)


def _read_ceiling(
    runtime: Runtime, model_request: ModelRequest, resident: Model | None
) -> int | None:
    """Find the most the model asked for could be served at.

    One catalogue read against a load costing tens of seconds, and none at all
    where the resident model has already been read or where no window was
    asked for and there is nothing to measure.

    A model the runtime does not have states no ceiling here. Refusing it by
    name is the runtime's own answer to make, with the address and what to run
    to list what there is.

    :param runtime: The runtime to ask what it has.
    :param model_request: The model a run asked for, and the window to hold it
        at.
    :param resident: The model already held, where the run named none and it
        was substituted in.

    :return: The model's ceiling, or ``None`` where nothing states one.

    :raise RuntimeUnreachableError: When the catalogue cannot be read.
    """
    if model_request.context_window is None:
        return None

    if resident is not None:
        return resident.context_ceiling

    return next(
        (
            model.context_ceiling
            for model in runtime.read_catalogue()
            if model.identifier == model_request.identifier
        ),
        None,
    )
