"""Claude Code, which speaks Anthropic's message API.

Its settings are environment variables, so a launch is an environment and an
argument list. Both are built rather than exported, so a caller can show them
before anything runs.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from offgrid.dialect import Dialect
from offgrid.exceptions import AgentSettingsError
from offgrid.model import Model

# Decode runs at tens of tokens per second, so thinking and long replies cost
# wall time directly.
MAX_OUTPUT_TOKENS = 8192

# Used when the runtime states no context for a model. Small enough to be
# served by anything, large enough to hold a conversation.
FALLBACK_CONTEXT = 32768

# WebSearch runs on Anthropic's servers. Pointed at a local model there is
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


@dataclass(frozen=True)
class Launch:
    """Everything needed to start the agent.

    :param env: Environment variables to add to the caller's own.
    :param argv: The command and its arguments.
    """

    env: dict[str, str]
    argv: list[str]


def dialect() -> Dialect:
    """Report the API shape Claude Code expects.

    :return: The Anthropic dialect.
    """
    return Dialect.ANTHROPIC


def plan(
    model: Model,
    *,
    host: str,
    config_dir: Path,
    token: str,
    passthrough: list[str] | None = None,
) -> Launch:
    """Work out how to start Claude Code against a local runtime.

    :param model: The model that will answer.
    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
    :param config_dir: Profile directory to use instead of the caller's own,
        which keeps their plugins and servers out of the cached prefix.
    :param token: Credential the local server ignores but the agent requires.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: The environment and command to run.
    """
    context = model.context_limit or FALLBACK_CONTEXT

    env = {
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "ANTHROPIC_BASE_URL": f"http://{host}",
        "ANTHROPIC_AUTH_TOKEN": token,
        "ANTHROPIC_MODEL": model.identifier,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model.identifier,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model.identifier,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model.identifier,
        "MAX_THINKING_TOKENS": "0",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(MAX_OUTPUT_TOKENS),
        # Compact before the server truncates the prefix and voids its cache.
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(context),
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1",
    }

    argv = [
        "claude",
        # No --mcp-config alongside it, so no servers load at all.
        "--strict-mcp-config",
        # Volatile sections move into the first message, leaving the cached
        # prefix identical between turns.
        "--exclude-dynamic-system-prompt-sections",
        *(passthrough or []),
    ]

    return Launch(env=env, argv=argv)


def prepare(config_dir: Path) -> None:
    """Make sure the agent has a profile to run against.

    The profile is its settings and the notes it reads at startup. Anything
    already there is left alone: both are meant to be edited, and a run is no
    place to lose those edits. The settings are read rather than trusted,
    because one of those edits can undo what they are for.

    :param config_dir: Profile directory to create if it is not there.

    :raise AgentSettingsError: When the settings already there cannot be read,
        or would let the agent search the web.
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    notes = config_dir / "CLAUDE.md"
    if not notes.exists():
        notes.write_text(INSTRUCTIONS)

    settings = config_dir / "settings.json"
    if not settings.exists():
        settings.write_text(json.dumps(SLIM_SETTINGS, indent=2) + "\n")
        return

    _require_no_search(settings)


def _require_no_search(settings: Path) -> None:
    """Refuse settings that would let the agent reach for WebSearch.

    :param settings: The agent's settings file.

    :raise AgentSettingsError: When it cannot be read, or does not deny it.
    """
    try:
        stored = json.loads(settings.read_text())
    except ValueError as error:
        raise AgentSettingsError(
            f"{settings} is not readable as JSON: {error}. Fix it, or delete it "
            "and offgrid writes one."
        ) from error

    permissions = stored.get("permissions") if isinstance(stored, dict) else None
    denied = permissions.get("deny") if isinstance(permissions, dict) else None

    if not isinstance(denied, list) or "WebSearch" not in denied:
        raise AgentSettingsError(
            f"{settings} does not deny WebSearch, which runs on Anthropic's "
            "servers: against a local model there is nothing to run it, so the "
            "model invents a result and the agent returns it as an answer. Add "
            "it to permissions.deny, or delete the file and offgrid writes one."
        )
