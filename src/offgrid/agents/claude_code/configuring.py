"""What offgrid writes into a fresh Claude Code directory, and refuses.

The settings and the notes are what a person edits, and what counts as a
denial is what the agent itself reads: a rule Claude Code does not honour is
not one offgrid may count as protection.
"""

SETTINGS = "settings.json"
NOTES = "CLAUDE.md"

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
