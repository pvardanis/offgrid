"""How Claude Code is started, and what is read out of what it is given.

What was passed is read beside what offgrid passes itself, because one
argument decides whether the settings file is loaded at all — and a deny in a
file nothing loads protects nothing.
"""

from offgrid.domain.running.agent import Passthrough

# Decode runs at tens of tokens per second, so thinking and long replies cost
# wall time directly.
MAX_OUTPUT_TOKENS = 8192

# The local server ignores it; Claude Code refuses to start without one, so it
# is a fact about this agent rather than about the runtime it is pointed at.
TOKEN = "local"

# Claude Code's system prompt and tool definitions do not fit below this, and
# what is on the other side of it is a failure at startup rather than a
# cramped session. A fact about this agent, so nothing may set it.
CONTEXT_FLOOR = 25_000

# Claude Code reads three sources, and this argument confines it to the ones
# it names. `user` is the one CLAUDE_CONFIG_DIR points at, so it is the one
# offgrid writes the deny into and the one a list may not leave out.
SOURCES = "--setting-sources"
WRITTEN_SOURCE = "user"


def get_claude_args(passthrough: Passthrough) -> list[str]:
    """Settle the command line Claude Code is started with.

    :param passthrough: Arguments handed to the agent unchanged.

    :return: The command and its arguments.
    """
    return [
        "claude",
        # No --mcp-config alongside it, so no servers load at all.
        "--strict-mcp-config",
        # Volatile sections move into the first message, leaving the cached
        # prefix identical between turns.
        "--exclude-dynamic-system-prompt-sections",
        *passthrough,
    ]


def get_dropped_settings_sources(passthrough: Passthrough) -> list[str] | None:
    """List the sources an argument confines the agent to, where it drops ours.

    A deny only binds where the file carrying it is loaded, and one argument
    decides that. Measured against claude 2.1.231, the rest of what `--help`
    suggests would defeat it does not: `deny` is applied where the tool list
    is built, so bypassing the permission checks never puts a denied tool
    back, and an `allow` loses to it.

    :param passthrough: What was handed to the agent unchanged.

    :return: The sources named, where they leave out the one offgrid writes —
        and none where the arguments still load it, or name none at all.
    """
    named = _read_setting_sources(passthrough)

    if named is None or WRITTEN_SOURCE in named:
        return None

    return named


def _read_setting_sources(passthrough: Passthrough) -> list[str] | None:
    """List the settings sources the arguments confine the agent to.

    The last of them, because that is the one Claude Code acts on: given the
    argument twice it takes the later value, so reading the first would pass
    the very line that drops the deny. Both spellings the agent accepts are
    read, and matching the flag at the start of an argument rather than
    anywhere inside one keeps a prompt that quotes it from counting as one.

    :param passthrough: What was handed to the agent unchanged.

    :return: The sources named last, or none where the arguments name none.
    """
    named = None

    for index, argument in enumerate(passthrough):
        if argument.startswith(f"{SOURCES}="):
            named = _split_sources(argument.split("=", 1)[1])
        elif argument == SOURCES and index + 1 < len(passthrough):
            named = _split_sources(passthrough[index + 1])

    return named


def _split_sources(value: str) -> list[str]:
    """Read one source per entry out of the value the argument carried.

    :param value: What the argument was given.

    :return: The sources it names.
    """
    return [source.strip() for source in value.split(",")]
