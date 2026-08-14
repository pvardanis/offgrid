"""How Claude Code is started, what it is given to work in, and what it refuses.

What may be passed is settled beside what offgrid passes itself, because one
argument decides whether the settings file is read at all — and a deny in a
file nothing loads protects nothing.
"""

from offgrid.exceptions import AgentSettingsError

# Decode runs at tens of tokens per second, so thinking and long replies cost
# wall time directly.
MAX_OUTPUT_TOKENS = 8192

# Used when the runtime states no context for a model. Small enough to be
# served by anything, large enough to hold a conversation.
FALLBACK_CONTEXT = 32768

# Claude Code reads three sources, and this argument confines it to the ones
# it names. `user` is the one CLAUDE_CONFIG_DIR points at, so it is the one
# offgrid writes the deny into and the one a list may not leave out.
SOURCES = "--setting-sources"
WRITTEN_SOURCE = "user"


def get_claude_args(passthrough: list[str]) -> list[str]:
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


def require_arguments_keep_the_settings_loaded(arguments: list[str]) -> None:
    """Refuse arguments that stop the settings file being read at all.

    A deny only binds where the file carrying it is loaded, and one argument
    decides that. Measured against claude 2.1.231, the rest of what `--help`
    suggests would defeat it does not: `deny` is applied where the tool list
    is built, so bypassing the permission checks never puts a denied tool
    back, and an `allow` loses to it.

    :param arguments: What was handed to the agent unchanged.

    :raise AgentSettingsError: When a list of sources leaves out the one
        offgrid wrote.
    """
    named = _read_setting_sources(arguments)

    if named is not None and WRITTEN_SOURCE not in named:
        raise AgentSettingsError(
            f"{SOURCES} {','.join(named)} does not name `{WRITTEN_SOURCE}`, which "
            "is the source offgrid writes its settings into, so nothing loads the "
            "deny on WebSearch and the agent is offered it again. Against a model "
            "on this machine there is nothing to run it, so the model invents a "
            f"result. Add `{WRITTEN_SOURCE}` to the list, or drop the argument."
        )


def _read_setting_sources(arguments: list[str]) -> list[str] | None:
    """List the settings sources the arguments confine the agent to.

    The last of them, because that is the one Claude Code acts on: given the
    argument twice it takes the later value, so reading the first would pass
    the very line that drops the deny. Both spellings the agent accepts are
    read, and matching the flag at the start of an argument rather than
    anywhere inside one keeps a prompt that quotes it from counting as one.

    :param arguments: What was handed to the agent unchanged.

    :return: The sources named last, or none where the arguments name none.
    """
    named = None

    for index, argument in enumerate(arguments):
        if argument.startswith(f"{SOURCES}="):
            named = _split_sources(argument.split("=", 1)[1])
        elif argument == SOURCES and index + 1 < len(arguments):
            named = _split_sources(arguments[index + 1])

    return named


def _split_sources(value: str) -> list[str]:
    """Read one source per entry out of the value the argument carried.

    :param value: What the argument was given.

    :return: The sources it names.
    """
    return [source.strip() for source in value.split(",")]
