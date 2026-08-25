"""Claude Code as an agent: what an agent is asked, in its terms.

Its settings are environment variables, so a launch is an environment and an
argument list. Both are built rather than exported, so a caller can show them
before anything runs.
"""

from dataclasses import dataclass, field

from offgrid.agents.claude_code.compacting import (
    explain_what_will_not_compact,
    get_compaction_setting,
)
from offgrid.agents.claude_code.config import ClaudeCodeConfig
from offgrid.agents.claude_code.configuring import (
    INSTRUCTIONS,
    NOTES,
    SETTINGS,
    SLIM_SETTINGS,
    get_denied_tools,
)
from offgrid.agents.claude_code.launching import (
    CONTEXT_FLOOR,
    MAX_OUTPUT_TOKENS,
    SOURCES,
    TOKEN,
    WRITTEN_SOURCE,
    get_claude_args,
    get_dropped_settings_sources,
)
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.keeping import (
    read_as_json,
    read_what_is_kept,
    write_settings_where_nothing_is_kept,
    write_where_nothing_is_kept,
)
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import AgentSettingsError


@dataclass(frozen=True)
class ClaudeCode:
    """Claude Code, run out of what a profile and a run settled for it.

    All of it is settled before a run starts, so all of it is bound rather
    than passed: what is read to decide whether a run is safe is then the same
    thing that is launched.

    `dialect` and `context_floor` are facts about Claude Code rather than
    about one binding, so they are settled here and not passed in.

    :param config: What the profile and the run settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.
    """

    config: ClaudeCodeConfig
    passthrough: Passthrough = ()
    dialect: Dialect = field(init=False, default=Dialect.ANTHROPIC)
    context_floor: int = field(init=False, default=CONTEXT_FLOOR)

    def configure(self) -> None:
        """Write the settings and the notes that are not there.

        Both are meant to be edited, so an edit is left as it is — including
        settings that leave WebSearch reachable, which the reading below
        reports rather than something this call writes over. A file that says
        nothing is not an edit, and is written into.

        :raise AgentSettingsError: When what is there cannot be read, or what
            is missing cannot be written.
        """
        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)

            write_where_nothing_is_kept(self.config.config_dir / NOTES, INSTRUCTIONS)
            write_settings_where_nothing_is_kept(
                self.config.config_dir / SETTINGS, SLIM_SETTINGS
            )
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
        # Whether there is anything to read is asked of the text, the same way
        # `configure` asks it. Read off what the text parses to, a file holding
        # `null` would be called empty and answered with the remedy for an
        # empty one — and that remedy is to run the command already running.
        body = read_what_is_kept(settings)

        if body is None:
            return HostedToolsReport(
                status=HostedToolsStatus.UNWRITTEN,
                detail=f"{settings} holds nothing, so nothing denies WebSearch.",
                remedy="`offgrid run` writes it before it starts the agent.",
            )

        if "WebSearch" in get_denied_tools(read_as_json(body, settings)):
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

        :return: The environment and command to run, and what a person is
            owed about the window it will run in.
        """
        served = model.context_window
        compaction, dropped = get_compaction_setting(served)

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
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1",
            **compaction,
        }

        return Launch(
            env=env,
            argv=get_claude_args(self.passthrough),
            dropped=dropped,
            caution=explain_what_will_not_compact(served),
        )
