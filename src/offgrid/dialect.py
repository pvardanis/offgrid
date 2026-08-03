"""The API shape a runtime serves and an agent expects."""

from enum import Enum


class Dialect(Enum):
    """An HTTP API shape for chat completions.

    Runtimes serve one; agents speak one. Where they differ, a translating
    proxy is required, and offgrid refuses the pair rather than bundling one.
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
