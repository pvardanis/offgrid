"""How OpenCode is started, and the configuration one run derives for it.

Everything offgrid derives is here rather than in the file `configure` writes,
because that call never overwrites: a derived value written once would be
silently wrong the moment the profile changed. It also keeps the address where
a person can be shown it before anything runs, which a file's contents cannot
be.

The two halves deep-merge, so what is here says only what a run settles.
"""

import json

from offgrid.agents.opencode.configuring import PROVIDER
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.model import Model

# Decode runs at tens of tokens per second, so a long reply costs wall time
# directly. The same cap the other adapter sets, for the same reason.
MAX_OUTPUT_TOKENS = 8192

# A conservative placeholder, not a measurement. This number was measured
# against Claude Code, and the evidence points the other way here — OpenCode's
# system prompt and tool definitions are roughly a quarter the size — so
# asserting it as OpenCode's own floor would be a false comment. The cost is
# windows refused that would probably have run, which is the safe direction.
# Issue #153 is the measurement.
CONTEXT_FLOOR = 25_000

# Where OpenCode reads the durable file, and the configuration a run derives.
# Both are read and deep-merged, which is what lets the half a person edits
# stay in a file while the half offgrid rebuilds every run travels here.
CONFIG_FILE = "OPENCODE_CONFIG"
CONFIG_CONTENT = "OPENCODE_CONFIG_CONTENT"


def get_opencode_args(passthrough: Passthrough) -> list[str]:
    """Settle the command line OpenCode is started with.

    Nothing of offgrid's own goes on it: which model answers is a key in the
    configuration this module derives, the same way the other adapter carries
    it in the launch's environment. So what a person typed is the whole of the
    command line after the command, in the order they typed it, and their own
    model flag beats offgrid's selection exactly as it does for the other
    adapter.

    :param passthrough: Arguments handed to the agent unchanged.

    :return: The command and its arguments.
    """
    return ["opencode", *passthrough]


def get_derived_configuration(model: Model, *, runtime_host: str) -> str:
    """Build everything offgrid derives, as configuration OpenCode reads inline.

    The model has to be enumerated: measured on opencode 1.18.20, a provider
    entry carrying the package and the address but no model list resolves no
    model at all, so naming the provider is not enough to reach one.

    :param model: The model that will answer.
    :param runtime_host: Address the runtime listens on.

    :return: The configuration, as OpenCode reads it from the environment.
    """
    return json.dumps(
        {
            "model": f"{PROVIDER}/{model.identifier}",
            "provider": {
                PROVIDER: {
                    "options": {"baseURL": f"http://{runtime_host}/v1"},
                    "models": {model.identifier: {"limit": _get_limits(model)}},
                }
            },
        }
    )


def _get_limits(model: Model) -> dict[str, int]:
    """Size what the model answers at, out of what the runtime settled on.

    The window rather than the ceiling, because the ceiling is what the model
    could be served at and the window is what it is being served at — telling
    OpenCode the larger of the two is asking it to compact after the runtime
    has already truncated the prefix.

    Where the runtime states no window, nothing is said about context and
    OpenCode falls back to its own default. A number invented here would be
    the same truncation, arrived at by guessing.

    :param model: The model that will answer.

    :return: What to put under the model's `limit`.
    """
    if model.context_window is None:
        return {"output": MAX_OUTPUT_TOKENS}

    return {"context": model.context_window, "output": MAX_OUTPUT_TOKENS}
