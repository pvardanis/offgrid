"""Claude Code as an agent: what an agent is asked, in its terms.

Its settings are environment variables, so a launch is an environment and an
argument list. Both are built rather than exported, so a caller can show them
before anything runs.
"""

import json
from dataclasses import dataclass, field

from offgrid.agents.claude_code.config import ClaudeCodeConfig
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
    SOURCES,
    TOKEN,
    WRITTEN_SOURCE,
    get_claude_args,
    get_dropped_settings_sources,
)
from offgrid.domain.dialect import Dialect
from offgrid.domain.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.launch import Launch
from offgrid.domain.model import Model
from offgrid.shared.exceptions import AgentSettingsError


@dataclass(frozen=True)
class ClaudeCode:
    """Claude Code, run out of what a profile and a run settled for it.

    All of it is settled before a run starts, so all of it is bound rather
    than passed: what is read to decide whether a run is safe is then the same
    thing that is launched.

    `dialect` is a fact about Claude Code rather than about one binding, so
    it is settled here and not passed in.

    :param config: What the profile and the run settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.
    """

    config: ClaudeCodeConfig
    passthrough: tuple[str, ...] = ()
    dialect: Dialect = field(init=False, default=Dialect.ANTHROPIC)

    def configure(self) -> None:
        """Write the settings and the notes that are not there.

        Both are meant to be edited, so what is already there is left as it
        is — including settings that leave WebSearch reachable, which are
        still an edit rather than something to write over.

        :raise AgentSettingsError: When what is missing cannot be written.
        """
        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)

            self._write_missing(NOTES, INSTRUCTIONS)
            self._write_missing(SETTINGS, json.dumps(SLIM_SETTINGS, indent=2) + "\n")
        except OSError as error:
            raise AgentSettingsError(
                f"{self.config.config_dir} cannot be written: {error}. Fix what is "
                "there or what owns it, and run again."
            ) from error

    def read_hosted_tools(self) -> HostedToolsReport:
        """Say whether WebSearch can still be reached from this run.

        Both halves of it, in the order they bite: an argument that stops the
        settings being loaded leaves them beside the point, however they read.

        :return: What it found, and what to change.

        :raise AgentSettingsError: When the settings are there and cannot be
            read, which says nothing either way about WebSearch.
        """
        dropped = get_dropped_settings_sources(self.passthrough)

        if dropped is not None:
            return HostedToolsReport(
                status=HostedToolsStatus.PERMITTED,
                detail=(
                    f"{SOURCES} {','.join(dropped)} does not name "
                    f"`{WRITTEN_SOURCE}`, so nothing loads the deny on WebSearch."
                ),
                remedy=f"Add `{WRITTEN_SOURCE}` to the list, or drop the argument.",
            )

        settings = self.config.config_dir / SETTINGS

        if not settings.exists():
            return HostedToolsReport(
                status=HostedToolsStatus.UNWRITTEN,
                detail=f"{settings} is not there, so nothing denies WebSearch.",
                remedy="`offgrid run` writes it before it starts the agent.",
            )

        if "WebSearch" in get_denied_tools(self._read_settings()):
            return HostedToolsReport(
                status=HostedToolsStatus.DENIED,
                detail=f"{settings} denies WebSearch.",
            )

        return HostedToolsReport(
            status=HostedToolsStatus.PERMITTED,
            detail=(
                f"{settings} does not deny WebSearch, which runs on Anthropic's "
                "servers: against a local model there is nothing to run it, so "
                "the model invents a result and the agent returns it as an answer."
            ),
            remedy=(
                "Add it to permissions.deny, or delete the file and offgrid writes one."
            ),
        )

    def plan(self, model: Model) -> Launch:
        """Work out how to start Claude Code against a local runtime.

        :param model: The model that will answer.

        :return: The environment and command to run.
        """
        context = model.context_limit or FALLBACK_CONTEXT

        env = {
            "CLAUDE_CONFIG_DIR": str(self.config.config_dir),
            "ANTHROPIC_BASE_URL": f"http://{self.config.runtime_host}",
            "ANTHROPIC_AUTH_TOKEN": TOKEN,
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

        return Launch(env=env, argv=get_claude_args(self.passthrough))

    def _write_missing(self, name: str, content: str) -> None:
        """Write one file of the configuration, unless it is already there.

        :param name: What the file is called inside the directory.
        :param content: What to write where there is nothing.

        :raise OSError: When it cannot be written.
        """
        written = self.config.config_dir / name

        if not written.exists():
            written.write_text(content)

    def _read_settings(self) -> object:
        """Read the settings file as whatever it holds.

        Reading is apart from parsing because bytes that are not text never
        reach the parser, and calling that bad JSON sends someone looking for
        a bracket. `UnicodeDecodeError` is a `ValueError`, so it would.

        :return: What the file holds, in whatever shape it was written.

        :raise AgentSettingsError: When it cannot be read, or is not JSON.
        """
        settings = self.config.config_dir / SETTINGS

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
