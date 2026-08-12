"""LM Studio, which serves Anthropic's message API alongside OpenAI's.

`connect` is the whole of what the registry asks for. What it answers with is
in `lmstudio.py`, and what that reaches for is beside it.
"""

from offgrid.runtime import Runtime
from offgrid.runtimes.lmstudio.lmstudio import LMStudio


def connect(host: str) -> Runtime:
    """Bind the address LM Studio listens on.

    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.

    :return: A connection offgrid can ask to hold a model.
    """
    return LMStudio(host=host)
