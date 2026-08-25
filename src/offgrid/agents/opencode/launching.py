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
# directly. The same cap the Claude Code adapter sets, for the same reason.
MAX_OUTPUT_TOKENS = 8192

# A conservative placeholder, not a measurement. This number was measured
# against Claude Code, and the evidence points the other way here — OpenCode
# sends a smaller prompt and tool set — so asserting it as OpenCode's own floor
# would be a false comment. The cost is windows refused that would probably
# have run, which is the safe direction. Issue #153 is the measurement.
CONTEXT_FLOOR = 25_000

# Where OpenCode reads the durable file, and the configuration a run derives.
#
# Neither replaces what a person already has. OpenCode reads their own
# configuration as well and deep-merges all three, so their provider entry,
# their key and their timeouts come through a run untouched — only a key
# offgrid names is overridden. Measured on opencode 1.18.20 with all three
# deliberately set to conflicting values:
#
#     inline  >  the file offgrid writes  >  a person's own configuration
#
# The first of those is what the split rests on, and it was measured both ways
# round: `configure` never overwrites its file once it is there, so an address
# hand-edited into it has to lose to the derived one — and a wrong address
# hangs rather than erroring, which is the failure nobody gets a message about.
#
# A configuration in the directory the run started from beats the file offgrid
# writes, though not what a run carries inline, so the address is safe either
# way — measured with a project file pointing the provider at a dead port,
# which answered through the derived address rather than stalling. What it is
# not safe from is everything else such a file states: providers, agents,
# permissions and instructions offgrid never writes and therefore cannot
# outrank. So the variable below stops OpenCode reading project configuration
# at all, covering the class rather than the one key.
#
# What that reaches, measured on opencode 1.18.20: an `opencode.json` or
# `.jsonc`, a `.opencode` directory, a project `tui.json`, and the instructions
# a project states in `AGENTS.md`, `CLAUDE.md` or `CONTEXT.md` — each of them
# searched for from the directory the run started in upwards, as far as the
# worktree root. A person's own configuration under their home is read either
# way.
CONFIG_FILE = "OPENCODE_CONFIG"
CONFIG_CONTENT = "OPENCODE_CONFIG_CONTENT"
PROJECT_CONFIG = "OPENCODE_DISABLE_PROJECT_CONFIG"

# What OpenCode reads as true. Measured on opencode 1.18.20: it lowercases the
# value and takes `1` or `true`, so anything else — `0`, `yes` and an empty
# string alike — leaves project configuration read.
PROJECT_CONFIG_DISABLED = "1"


def get_opencode_args(passthrough: Passthrough) -> list[str]:
    """Settle the command line OpenCode is started with.

    Nothing of offgrid's own goes on it: which model answers is a key in the
    configuration this module derives, the same way the Claude Code adapter
    carries it in the launch's environment. So what a person typed is the whole
    of the command line after the command, in the order they typed it.

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
                    "models": {model.identifier: _describe_the_model(model)},
                }
            },
        }
    )


def _describe_the_model(model: Model) -> dict[str, dict[str, int]]:
    """Say what the model answers at, out of what the runtime settled on.

    The window rather than the ceiling, because the ceiling is what the model
    could be served at and the window is what it is being served at — telling
    OpenCode the larger of the two is asking it to compact after the runtime
    has already truncated the prefix.

    Where the runtime states no window there is no `limit` at all, rather than
    one naming an output cap alone. Measured on opencode 1.18.20: the published
    schema requires `context` and `output` together, and a `limit` carrying one
    of them is refused as an invalid configuration before a token is generated.
    Omitting it entirely is accepted. So the output cap goes with the window,
    which is a real loss — issue #154 is what a person is owed about it.

    :param model: The model that will answer.

    :return: The model's entry, which is empty where the runtime states no
        window to size it from.
    """
    if model.context_window is None:
        return {}

    return {"limit": {"context": model.context_window, "output": MAX_OUTPUT_TOKENS}}
