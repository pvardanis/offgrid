"""Claude Code, which speaks Anthropic's message API.

Its settings are environment variables, so a launch is an environment and an
argument list. Both are built rather than exported, so a caller can show them
before anything runs.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from offgrid.agent import Agent
from offgrid.dialect import Dialect
from offgrid.exceptions import AgentSettingsError
from offgrid.launch import Launch
from offgrid.model import Model

SETTINGS = "settings.json"
NOTES = "CLAUDE.md"

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


def _environment(
    model: Model, *, host: str, token: str, config: Path
) -> dict[str, str]:
    """Settle everything Claude Code reads out of its environment.

    :param model: The model that will answer.
    :param host: Address the runtime listens on.
    :param token: Credential the local server ignores but the agent requires.
    :param config: Where the agent's own configuration is kept.

    :return: What to add to the environment offgrid was started with.
    """
    context = model.context_limit or FALLBACK_CONTEXT

    return {
        "CLAUDE_CONFIG_DIR": str(config),
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


def _arguments(passthrough: list[str]) -> list[str]:
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


def _what_is_denied(stored: object) -> Sequence[object]:
    """List what a settings file denies the agent.

    A shape the agent itself does not read denies nothing: `deny` typed as a
    word rather than a list is not a rule Claude Code honours, so it is not
    one offgrid may count.

    :param stored: What the settings file held.

    :return: The entries it denies, whatever they turned out to be, and none
        where its shape says nothing.
    """
    permissions = stored.get("permissions") if isinstance(stored, dict) else None
    denied = permissions.get("deny") if isinstance(permissions, dict) else None

    return denied if isinstance(denied, list) else []


def prepare(config_dir: Path) -> Agent:
    """Bind the directory Claude Code keeps its configuration in.

    :param config_dir: Profile directory to use instead of the caller's own,
        which keeps their plugins and servers out of the cached prefix.

    :return: An agent offgrid can configure and start.
    """
    return ClaudeCode(config_dir=config_dir)


@dataclass(frozen=True)
class ClaudeCode:
    """Claude Code, run out of the directory it was bound to.

    `dialect` is a fact about Claude Code rather than about one directory, so
    it is settled here and not passed in.

    :param config_dir: Where its settings and its notes are kept.
    """

    config_dir: Path
    dialect: Dialect = field(init=False, default=Dialect.ANTHROPIC)

    def configure(self) -> None:
        """Write the settings and the notes that are not there.

        Both are meant to be edited, so what is already there is left as it
        is — including settings the guard would refuse, which are still an
        edit rather than something to write over.

        :raise AgentSettingsError: When what is missing cannot be written.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            self._write_missing(NOTES, INSTRUCTIONS)
            self._write_missing(SETTINGS, json.dumps(SLIM_SETTINGS, indent=2) + "\n")
        except OSError as error:
            raise AgentSettingsError(
                f"{self.config_dir} cannot be written: {error}. Fix what is "
                "there or what owns it, and run again."
            ) from error

    def require_hosted_tools_denied(self) -> None:
        """Refuse settings that would let the agent reach for WebSearch.

        :raise AgentSettingsError: When the settings are absent, cannot be
            read, or do not deny it.
        """
        settings = self.config_dir / SETTINGS

        if "WebSearch" not in _what_is_denied(self._read_settings()):
            raise AgentSettingsError(
                f"{settings} does not deny WebSearch, which runs on Anthropic's "
                "servers: against a local model there is nothing to run it, so the "
                "model invents a result and the agent returns it as an answer. Add "
                "it to permissions.deny, or delete the file and offgrid writes one."
            )

    def _write_missing(self, name: str, content: str) -> None:
        """Write one file of the configuration, unless it is already there.

        :param name: What the file is called inside the directory.
        :param content: What to write where there is nothing.

        :raise OSError: When it cannot be written.
        """
        written = self.config_dir / name

        if not written.exists():
            written.write_text(content)

    def _require_settings_file(self) -> Path:
        """Answer with the settings file, which has to be there to deny.

        :return: The path to it.

        :raise AgentSettingsError: When it is not there.
        """
        settings = self.config_dir / SETTINGS

        if not settings.exists():
            raise AgentSettingsError(
                f"{settings} is not there, so nothing denies WebSearch. "
                "`offgrid run` writes it before it starts the agent."
            )

        return settings

    def _read_settings(self) -> object:
        """Read the settings file as whatever it holds.

        Reading is apart from parsing because bytes that are not text never
        reach the parser, and calling that bad JSON sends someone looking for
        a bracket. `UnicodeDecodeError` is a `ValueError`, so it would.

        :return: What the file holds, in whatever shape it was written.

        :raise AgentSettingsError: When it is absent, cannot be read, or is
            not JSON.
        """
        settings = self._require_settings_file()

        try:
            body = settings.read_text()
        except (OSError, UnicodeDecodeError) as error:
            raise AgentSettingsError(
                f"{settings} cannot be read: {error}. Fix what it is or what "
                "owns it, or delete it and offgrid writes one."
            ) from error

        try:
            return json.loads(body)
        except ValueError as error:
            raise AgentSettingsError(
                f"{settings} is not readable as JSON: {error}. Fix it, or delete it "
                "and offgrid writes one."
            ) from error

    def plan(
        self,
        model: Model,
        *,
        host: str,
        token: str,
        passthrough: list[str],
    ) -> Launch:
        """Work out how to start Claude Code against a local runtime.

        :param model: The model that will answer.
        :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
        :param token: Credential the local server ignores but the agent
            requires.
        :param passthrough: Arguments handed to the agent unchanged.

        :return: The environment and command to run.
        """
        return Launch(
            env=_environment(model, host=host, token=token, config=self.config_dir),
            argv=_arguments(passthrough),
        )
