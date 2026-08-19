"""Which windows a run cannot be held at, and why each is refused.

A window is bounded at both ends by something other than itself: the agent
below, which does not start in one too small for its own prompt, and the model
above, which cannot honour more than it states. Both are knowable before a
load, and a load is tens of seconds nobody gets back — which is where the
dialect check already sits, for the same reason.
"""

from offgrid.domain.running.model import ModelRequest
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


def refuse_a_window_above_the_ceiling(
    model_request: ModelRequest, ceiling: int | None
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
