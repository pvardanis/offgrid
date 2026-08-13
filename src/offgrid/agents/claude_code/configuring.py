"""What offgrid writes into a fresh Claude Code directory, and refuses.

The settings and the notes are what a person edits, and what counts as a
denial is what the agent itself reads: a rule Claude Code does not honour is
not one offgrid may count as protection. That is why the arguments are read
here too — one of them decides whether the file is loaded at all, and a deny
in a file nothing loads is no more protection than a shape nothing honours.
"""

from offgrid.exceptions import AgentSettingsError

SETTINGS = "settings.json"
NOTES = "CLAUDE.md"

# Claude Code reads three sources, and this argument confines it to the ones
# it names. `user` is the one CLAUDE_CONFIG_DIR points at, so it is the one
# offgrid writes the deny into and the one a list may not leave out.
SOURCES = "--setting-sources"
WRITTEN_SOURCE = "user"

# nothing to run it, so the model emits a tool call as prose and the agent
# returns it as a result: an invented answer, with no error.
SLIM_SETTINGS = {
    "$schema": "https://json.schemastore.org/claude-code-settings.json",
    "permissions": {"deny": ["WebSearch"]},
    "enableAllProjectMcpServers": False,
    "enabledPlugins": {},
    "alwaysThinkingEnabled": False,
}


# Said once in the profile rather than discovered by calling the tool, which
# costs a turn — and locally a turn is tens of seconds.
INSTRUCTIONS = """# Answering from a model on this machine

WebSearch is denied here. It runs on Anthropic's servers, and this session
answers from a model held on this machine, so the call comes back as invented
results rather than as an error. Nothing replaces it yet.

WebFetch does work: use it whenever a URL is known. Where one is not, say what
could not be looked up rather than answering from memory.
"""


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


def get_denied_tools(stored: object) -> list[str]:
    """List the tools a settings file denies the agent.

    A shape the agent itself does not read denies nothing, and each of these
    is one: `deny` typed as a word rather than a list, a mapping where a list
    belongs, an entry that is not the name of a tool. None of them is a rule
    Claude Code honours, so none is one offgrid may count.

    :param stored: What the settings file held, in whatever shape it holds it.

    :return: The tools it denies, which is none where its shape says nothing.
    """
    permissions = stored.get("permissions") if isinstance(stored, dict) else None
    denied = permissions.get("deny") if isinstance(permissions, dict) else None

    if not isinstance(denied, list):
        return []

    return [tool for tool in denied if isinstance(tool, str)]
