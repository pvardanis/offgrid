"""Claude Code as an agent: what an agent is asked, in its terms.

Its settings are environment variables, so a launch is an environment and an
argument list. Both are built rather than exported, so a caller can show them
before anything runs.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from offgrid.agents.claude_code.configuring import (
    INSTRUCTIONS,
    NOTES,
    SETTINGS,
    SLIM_SETTINGS,
    get_denied_tools,
)
from offgrid.agents.claude_code.launching import (
    FALLBACK_CONTEXT,
    MAX_OUTPUT_TOKENS,
    get_claude_args,
)
from offgrid.dialect import Dialect
from offgrid.exceptions import AgentSettingsError
from offgrid.launch import Launch
from offgrid.model import Model


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

        The settings offgrid wrote, which is what it can answer for. Claude
        Code takes `--dangerously-skip-permissions`, `--permission-mode
        bypassPermissions` and `--setting-sources`, and each of them can leave
        this passing while the deny is unenforced or unread (#65).

        :raise AgentSettingsError: When the settings are absent, cannot be
            read, or do not deny it.
        """
        settings = self.config_dir / SETTINGS

        if "WebSearch" not in get_denied_tools(self._read_settings()):
            raise AgentSettingsError(
                f"{settings} does not deny WebSearch, which runs on Anthropic's "
                "servers: against a local model there is nothing to run it, so the "
                "model invents a result and the agent returns it as an answer. Add "
                "it to permissions.deny, or delete the file and offgrid writes one."
            )

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
        context = model.context_limit or FALLBACK_CONTEXT

        env = {
            "CLAUDE_CONFIG_DIR": str(self.config_dir),
            "ANTHROPIC_BASE_URL": f"http://{host}",
            "ANTHROPIC_AUTH_TOKEN": token,
            "ANTHROPIC_MODEL": model.identifier,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model.identifier,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model.identifier,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model.identifier,
            "MAX_THINKING_TOKENS": "0",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(MAX_OUTPUT_TOKENS),
            # Compact before the server truncates the prefix and voids its
            # cache.
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(context),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1",
        }

        return Launch(env=env, argv=get_claude_args(passthrough))

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
