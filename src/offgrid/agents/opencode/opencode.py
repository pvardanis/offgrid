"""OpenCode as an agent: what an agent is asked, in its terms.

Its settings are a file it is pointed at and configuration it reads inline, so
a launch carries both — the second rebuilt every run, which is what keeps
nothing offgrid derives able to go stale.
"""

from dataclasses import dataclass, field

from offgrid.agents.opencode.cautioning import say_what_the_run_costs
from offgrid.agents.opencode.config import OpenCodeConfig
from offgrid.agents.opencode.configuring import (
    CONTINUE,
    DATA_HOME,
    DURABLE,
    LISTING,
    OFFERS_RESUMING,
    READS_THE_STORE,
    SESSION,
    SETTINGS,
    STATE,
    STATE_HOME,
    STORE,
)
from offgrid.agents.opencode.hosted_tools import read_hosted_tools
from offgrid.agents.opencode.launching import (
    COMMAND,
    CONFIG_CONTENT,
    CONFIG_FILE,
    CONTEXT_FLOOR,
    PROJECT_CONFIG,
    PROJECT_CONFIG_DISABLED,
    get_derived_configuration,
    get_opencode_args,
)
from offgrid.agents.opencode.sharing import read_transcript_sharing
from offgrid.domain.running.agent import AgentTerms, Passthrough
from offgrid.domain.running.config_editing import write_settings_where_nothing_is_kept
from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.leaving import Reading
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import AgentSettingsError

TERMS = AgentTerms(dialect=Dialect.OPENAI, context_floor=CONTEXT_FLOOR, command=COMMAND)
"""What OpenCode states about itself, which no binding of it may change."""


@dataclass(frozen=True)
class OpenCode:
    """OpenCode, run out of what a profile and a run settled for it.

    All of it is settled before a run starts, so all of it is bound rather
    than passed: what is read to decide whether a run is safe is then the same
    thing that is launched.

    What it states about itself is a fact about OpenCode rather than about one
    binding, so it is settled here and not passed in.

    :param config: What the profile and the run settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.
    """

    config: OpenCodeConfig
    passthrough: Passthrough = ()
    terms: AgentTerms = field(init=False, default=TERMS)

    def configure(self) -> None:
        """Write the provider entry that is not there.

        Only what offgrid never revises, and only where there is no edit to
        lose: the file is meant to be edited, and a person who turned sharing
        back on keeps that. A file that says nothing is written into rather
        than left, because `share` is written here and nothing states a
        default for it — an emptied file makes no promise about whether a
        transcript leaves this machine.

        What keeps that from being silent is `leaving.py`, which reads the key
        back: an edit this call will not write into is one a run refuses on,
        naming the file and the value to set.

        :raise AgentSettingsError: When what is there cannot be read, or what
            is missing cannot be written.
        """
        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)

            write_settings_where_nothing_is_kept(
                self.config.config_dir / SETTINGS, DURABLE
            )
        except OSError as error:
            raise AgentSettingsError(
                f"{self.config.config_dir} cannot be written: {error}. Fix what is "
                "there or what owns it, and run again."
            ) from error

    def read_what_leaves_this_machine(self) -> tuple[Reading, ...]:
        """Say what this run could send off this machine, one way at a time.

        Each subject is read where it is settled and says so in its own
        module: nothing hosted from a tool list read off a live server, sharing
        from the command line and then from the key in the file `configure`
        writes and leaves alone.

        :return: One reading for each way off this machine.

        :raise AgentSettingsError: When the file is there and cannot be read,
            which says nothing either way about sharing.
        """
        return (
            read_hosted_tools(),
            read_transcript_sharing(
                self.config.config_dir / SETTINGS, self.passthrough
            ),
        )

    @property
    def conversations(self) -> Conversations:
        """Where a conversation this run starts is kept, and the way back in.

        The same store the launch points `XDG_DATA_HOME` at, because that
        variable is what moves the database a session lands in. The layout
        beneath it is not named: the `opencode/` hung off that value, and the
        database and write-ahead log inside it, are OpenCode's own.

        :return: Where they are kept, and how to open one again.
        """
        return Conversations(
            kept_in=self.config.config_dir / STORE,
            resume_with=(
                f"`offgrid run -- run {CONTINUE}` takes up the last one and "
                f"`offgrid run -- run {SESSION} <id>` one by identifier"
            ),
            measured=(
                f"measured against {OFFERS_RESUMING}. To read what is there "
                f"without holding a model, point `{DATA_HOME}` at it and run "
                f"`opencode {LISTING}`: measured against {READS_THE_STORE}, "
                "that listing answers out of the store the variable names."
            ),
        )

    def plan(self, model: Model) -> Launch:
        """Work out how to start OpenCode against a local runtime.

        :param model: The model that will answer.

        :return: The environment and command to run, and what a person is
            owed before it starts.
        """
        env = {
            CONFIG_FILE: str(self.config.config_dir / SETTINGS),
            CONFIG_CONTENT: get_derived_configuration(
                model, runtime_host=self.config.runtime_host
            ),
            PROJECT_CONFIG: PROJECT_CONFIG_DISABLED,
            DATA_HOME: str(self.config.config_dir / STORE),
            STATE_HOME: str(self.config.config_dir / STATE),
        }

        return Launch(
            env=env,
            argv=get_opencode_args(self.passthrough),
            caution=say_what_the_run_costs(model.context_window),
        )
