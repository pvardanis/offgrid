"""What a run will ask for, put into words before it asks.

`answering.py` is what the runtime does with a request. This is the request
read back to whoever wrote it, so the number a run will ask for can be
compared with the one being served without paying for a load to find out.
"""

from offgrid.domain.running.model import ModelRequest


def describe_what_is_asked_for(request: ModelRequest) -> str:
    """Say what a run will ask of the runtime, for reading beside its answer.

    :param request: What the run will ask for.

    :return: The sentence to print.
    """
    if request.identifier is None and request.context_window is None:
        return "asks for nothing, so a run takes whatever is held"

    if request.context_window is None:
        return f"{request.identifier}, at whatever it is served at"

    if request.identifier is None:
        return f"whatever is held, at {request.context_window}"

    return f"{request.identifier} at {request.context_window}"
