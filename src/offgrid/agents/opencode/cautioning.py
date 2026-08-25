"""What a person is owed before an OpenCode run starts, and why each of it.

Two things a run does that somebody would otherwise meet mid-session: it takes
project configuration away from every run, and it leaves a run nobody stated a
window for unsized. They are read together because they are lost together, so
they are settled in one place and said as one thing.
"""

from offgrid.agents.opencode.configuring import SETTINGS
from offgrid.agents.opencode.launching import MAX_OUTPUT_TOKENS

# Said as a standing fact about an offgrid run rather than conditioned on
# whether such a file is there. Deciding that would mean reimplementing
# OpenCode's own upward directory walk, its stopping condition and both file
# spellings, to word one sentence — and a walk that drifted from theirs would
# say the wrong thing confidently. For the same reason it names what a person
# is likeliest to have rather than claiming a complete list.
PROJECT_CONFIG_CAUTION = (
    "Project configuration is not read for this run: an `opencode.json`, a "
    "`.opencode` directory and instructions such as `AGENTS.md` are skipped, "
    "in the directory you started from and every directory above it up to the "
    "project root. offgrid cannot outrank the providers, agents and "
    "permissions one of those adds, so it runs with none of them. Your own "
    "configuration under your home is read as usual. Start OpenCode yourself "
    "to use what a project states."
)

# What a run loses where the runtime states no window, and the two places a
# person can state one instead. Both halves go, because the published schema
# takes `context` and `output` as a pair: measured on opencode 1.18.23, a
# `limit` naming a context and no output is refused as an invalid
# configuration before a token is generated, so the output cap cannot outlive
# the window it travels with.
#
# The second remedy was measured the same day and the same way: a `limit` a
# person writes into the file offgrid keeps survives into the run, because
# what a launch derives states an empty entry for the model rather than a
# competing one, and the two deep-merge. So the sentence sends somebody to a
# file that will actually be read.
#
# What it does not do is name a number of its own. A window offgrid guessed is
# the same truncation, arrived at by guessing.
UNSTATED_WINDOW_CAUTION = (
    "The runtime states no window for this model, so nothing sizes this run: "
    "OpenCode answers at its own context default and its own output default "
    f"— rather than the {MAX_OUTPUT_TOKENS}-token reply cap a stated window "
    "gets — and the runtime truncates the prefix at whatever it is really "
    "serving, part-way through the session. Start again with `offgrid run "
    "--context-window` to hold the model at a window you choose, or write a "
    "`limit` naming both `context` and `output` for this model into the "
    f"`{SETTINGS}` offgrid keeps for the agent."
)


def say_what_the_run_costs(window: int | None) -> str:
    """Say everything this run does that a person would otherwise meet later.

    :param window: What the model is being served at, or ``None`` where the
        runtime states nothing.

    :return: What to tell a person before the run starts.
    """
    if window is not None:
        return PROJECT_CONFIG_CAUTION

    return f"{PROJECT_CONFIG_CAUTION}\n\n{UNSTATED_WINDOW_CAUTION}"
