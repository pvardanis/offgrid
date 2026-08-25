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
)
from offgrid.agents.claude_code.launching import (
    CONTEXT_FLOOR,
    MAX_OUTPUT_TOKENS,
    TOKEN,
    get_claude_args,
)
from offgrid.agents.claude_code.leaving import read_what_leaves_this_machine
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.config_editing import (
    write_config_where_nothing_is_kept,
    write_settings_where_nothing_is_kept,
)
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.leaving import Reading
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

            write_config_where_nothing_is_kept(
                self.config.config_dir / NOTES, INSTRUCTIONS
            )
            write_settings_where_nothing_is_kept(
                self.config.config_dir / SETTINGS, SLIM_SETTINGS
            )
        except OSError as error:
            raise AgentSettingsError(
                f"{self.config.config_dir} cannot be written: {error}. Fix what is "
                "there or what owns it, and run again."
            ) from error

    def read_what_leaves_this_machine(self) -> tuple[Reading, ...]:
        """Say what this run could send off this machine, one way at a time.

        Where each is read, and why it is read where it is, is in
        `leaving.py` — WebSearch out of a settings file and the argument
        deciding whether it is loaded, publishing out of the command line.

        :return: One reading for each way off this machine.

        :raise AgentSettingsError: When the settings are there and cannot be
            read, which says nothing either way about either.
        """
        return read_what_leaves_this_machine(
            self.config.config_dir / SETTINGS, self.passthrough
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
