"""Holding the model that will answer.

One machine, one pool of memory: what is held is memory the rest of the
machine cannot use, so the model that answers is held alone and goes when the
agent is done with it.

What reaching that state costs is the runtime's business, and each one reaches
it differently. This is where offgrid says which model it wants held.
"""

from offgrid.domain.running.context_window import (
    get_model_ceiling,
    refuse_a_window_above_the_ceiling,
    refuse_a_window_below_the_floor,
)
from offgrid.domain.running.discarding import WasWindowRefusedFunc
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.runtime import Runtime
from offgrid.shared.exceptions import ModelUnavailableError


def find_resident_model(runtime: Runtime) -> Model | None:
    """Find the model the runtime is already holding, where it holds one.

    Holding nothing is an answer, not a fault, for a caller that only looks.

    :param runtime: The runtime to ask.

    :return: The model the runtime is holding, or ``None`` where it holds none.

    :raise RuntimeUnreachableError: When the runtime cannot be reached.
    """
    return name_what_would_answer(runtime.read_held())


def name_what_would_answer(in_memory: list[Model]) -> Model | None:
    """Say which of the models a runtime is holding would answer a run.

    Beside the call that asks rather than inside it, because a caller that
    wants what is held *and* which of it answers would otherwise ask twice —
    and two readings are two moments, in which a model can be let go of.

    :param in_memory: What the runtime said it is holding.

    :return: The model that would answer, or ``None`` where it holds none.
    """
    # A runtime can hold several, and the port promises a stable order: the
    # first of them is the one offgrid names.
    return in_memory[0] if in_memory else None


def get_resident_model(runtime: Runtime) -> Model:
    """Find the model the runtime is already holding.

    :param runtime: The runtime to ask.

    :return: The model that would answer.

    :raise ModelUnavailableError: When the runtime holds none.
    :raise RuntimeUnreachableError: When it cannot be reached.
    """
    resident = find_resident_model(runtime)

    if resident is None:
        raise ModelUnavailableError(
            "The runtime is holding no model. Load a model in it, then try again."
        )

    return resident


def hold_model(
    runtime: Runtime,
    model_request: ModelRequest,
    *,
    context_floor: int,
    was_window_refused_func: WasWindowRefusedFunc,
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
    :param was_window_refused_func: Whether this runtime refused a model this window
        before. Asked once the model is named, since a run may have named
        none and be answered with the resident one.

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
        model_request, ceiling=get_model_ceiling(runtime, model_request, resident)
    )

    # A window this runtime refused before is not put to it again: asking
    # costs a release and a load that change nothing, and the load throws away
    # the prefix the runtime had cached. See #136.
    window = model_request.context_window

    if window is not None and was_window_refused_func(
        str(model_request.identifier), window
    ):
        model_request = model_request.model_copy(update={"context_window": None})

    return runtime.ensure_only(model_request)
