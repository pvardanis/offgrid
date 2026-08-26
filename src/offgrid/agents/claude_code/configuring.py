"""What offgrid writes into a fresh Claude Code directory, and reads back.

The settings and the notes are what a person edits, and what counts as a
denial is what the agent itself reads: a rule Claude Code does not honour is
not one offgrid may count as protection.

What that directory holds besides them is here too. It carries the
conversations as well as the settings, which is a fact about the variable
pointing at it rather than anything offgrid writes.
"""

SETTINGS = "settings.json"
NOTES = "CLAUDE.md"

# What `claude --help` offers at the version below: `-r, --resume [value]`,
# "Resume a conversation by session ID, or open interactive picker with
# optional search term".
RESUME = "--resume"
OFFERS_RESUME = "claude 2.1.246"

# `CLAUDE_CONFIG_DIR` decides where conversations are written as well as where
# settings are read, measured against the version below and recorded in
# `docs/decisions.md`: pointing it at offgrid's own directory moved every
# conversation there with it, which is why `claude --resume <id>` outside a run
# answers "No conversation found with session ID" for a session offgrid started
# minutes earlier. No argument or variable separates where conversations are
# written from where settings are read, so it is a fact about the directory
# rather than a choice offgrid makes twice.
#
# The two stamps differ because the readings do: one off `--help`, one from a
# run that moved the directory. Stamping both with either would claim a reading
# nobody took.
CARRIES_CONVERSATIONS = "claude 2.1.245"

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
