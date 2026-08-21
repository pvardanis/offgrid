"""Which windows a run cannot be held at, and the numbers deciding that.

A window is bounded at both ends by something other than itself: the agent
below, which does not start in one too small for its own prompt, and the model
above, which cannot honour more than it states. Both are knowable before a
load, and a load is tens of seconds nobody gets back — which is where the
dialect check already sits, for the same reason.

Reading the ceiling lives here rather than beside the caller, because it is
the one thing that asks the runtime for a number nothing else in this module
asks for — and the refusal it feeds is the only reader of it.

Each refusal takes what is being measured first and the bound it is measured
against by name. Two numbers of the same type read the same way round either
way, so naming the bound is what stops a caller handing them over swapped and
inverting the comparison with nothing to see.
"""

from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.runtime import Runtime
from offgrid.shared.exceptions import ContextWindowUnworkableError


def refuse_a_window_below_the_floor(window: int | None, *, floor: int) -> None:
    """Refuse a window the agent could not start in.

    Asked to start in one too small, the agent fails as it launches — after a
    load has already been paid for.

    :param window: The window a run asked for, or ``None`` where it asked for
        none and the runtime's own stands.
    :param floor: The smallest window the agent can start in.

    :raise ContextWindowUnworkableError: When the window is below the floor.
    """
    if window is None or window >= floor:
        return

    raise ContextWindowUnworkableError(
        f"A window of {window} is below the agent's floor of {floor}. Its "
        f"prompt and tool definitions do not fit in one that small, so it "
        f"would fail at startup. Ask for {floor} or more."
    )


def refuse_a_served_window_below_the_floor(model: Model, *, floor: int) -> None:
    """Refuse a run the runtime is serving too small a window for.

    The window asked for and the window served are different numbers, and
    only the second one starts the agent. A run that asked for nothing
    inherits whatever the runtime last remembered, and a run that asked is
    answered by a runtime free to honour it with a different number — so the
    floor is measured again against what came back.

    The load is already paid for by the time this can be checked, which is
    why it is not the same refusal as the one before it. What it saves is the
    agent starting and failing on its own terms, where the error is about an
    initial prompt rather than about the window that could not hold it.

    :param model: The model as the runtime serves it.
    :param floor: The smallest window the agent can start in.

    :raise ContextWindowUnworkableError: When the served window is below the
        floor. A model served at nothing stated passes: there is no number to
        measure, and the runtime rather than offgrid decides what it means.
    """
    window = model.context_window
    if window is None or window >= floor:
        return

    raise ContextWindowUnworkableError(
        f"The runtime is serving {model.identifier} at {window}, below the "
        f"agent's floor of {floor}. Its prompt and tool definitions do not "
        f"fit in one that small, so it would fail at startup. Ask for {floor} "
        "or more with --context-window, or serve it at more than that."
    )


def refuse_a_window_above_the_ceiling(
    model_request: ModelRequest, *, ceiling: int | None
) -> None:
    """Refuse a window the model could not honour.

    The runtime will not: asked for a window above a model's own stated
    maximum, LM Studio answers that it loaded it and reports the impossible
    number back, so nothing downstream can tell it is not real.

    A model the runtime states no ceiling for passes through, there being
    nothing to measure against.

    :param model_request: The model a run asked for, and the window to hold it
        at. Its identifier is settled by the time it reaches here.
    :param ceiling: The most that model could be served at, or ``None`` where
        the runtime states none.

    :raise ContextWindowUnworkableError: When the window is above the ceiling.
    """
    window = model_request.context_window
    if window is None or ceiling is None or window <= ceiling:
        return

    raise ContextWindowUnworkableError(
        f"A window of {window} is above {model_request.identifier}'s ceiling "
        f"of {ceiling}. The runtime would take it and serve a number the "
        f"model cannot honour. Ask for {ceiling} or less."
    )


def read_the_ceiling(
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
