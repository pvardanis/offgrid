"""OpenCode as an agent: what an agent is asked, in its terms.

Its settings are a file it is pointed at and configuration it reads inline, so
a launch carries both — the second rebuilt every run, which is what keeps
nothing offgrid derives able to go stale.
"""

import json
from dataclasses import dataclass, field

from offgrid.agents.opencode.config import OpenCodeConfig
from offgrid.agents.opencode.configuring import DURABLE, SETTINGS
from offgrid.agents.opencode.launching import (
    CONFIG_CONTENT,
    CONFIG_FILE,
    CONTEXT_FLOOR,
    PROJECT_CONFIG,
    PROJECT_CONFIG_CAUTION,
    PROJECT_CONFIG_DISABLED,
    get_derived_configuration,
    get_opencode_args,
)
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsReport, HostedToolsStatus
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import AgentSettingsError

# What was measured, so that "nothing hosted" reads as a fact about a version
# rather than as an adapter whose author never asked the question. Measured on
# 2026-08-24 the way `docs/decisions.md` measured 1.18.14, by reading the tool
# list it sends: bash, edit, glob, grep, read, skill, task, todowrite, webfetch
# and write — the same ten, and every one of them runs on this machine.
MEASURED_AGAINST = "opencode 1.18.20"


@dataclass(frozen=True)
class OpenCode:
    """OpenCode, run out of what a profile and a run settled for it.

    All of it is settled before a run starts, so all of it is bound rather
    than passed: what is read to decide whether a run is safe is then the same
    thing that is launched.

    `dialect` and `context_floor` are facts about OpenCode rather than about
    one binding, so they are settled here and not passed in.

    :param config: What the profile and the run settled for this agent.
    :param passthrough: Arguments handed to the agent unchanged.
    """

    config: OpenCodeConfig
    passthrough: Passthrough = ()
    dialect: Dialect = field(init=False, default=Dialect.OPENAI)
    context_floor: int = field(init=False, default=CONTEXT_FLOOR)

    def configure(self) -> None:
        """Write the provider entry that is not there.

        Only what offgrid never revises, and only where there is nothing: the
        file is meant to be edited, and a person who turned sharing back on
        keeps that.

        :raise AgentSettingsError: When what is missing cannot be written.
        """
        written = self.config.config_dir / SETTINGS

        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)

            if not written.exists():
                written.write_text(json.dumps(DURABLE, indent=2) + "\n")
        except OSError as error:
            raise AgentSettingsError(
                f"{self.config.config_dir} cannot be written: {error}. Fix what is "
                "there or what owns it, and run again."
            ) from error

    def read_hosted_tools(self) -> HostedToolsReport:
        """Say that OpenCode offers no tool offgrid cannot run here.

        Every tool it offers runs on this machine, and it speaks to whatever
        provider it is pointed at rather than to one vendor's servers, so there
        is nothing server-side to deny. Dated, because that is a fact about a
        version rather than a standing property of the agent.

        :return: That there is nothing to permit, and what that was measured
            against.
        """
        return HostedToolsReport(
            status=HostedToolsStatus.NONE_OFFERED,
            detail=(
                f"Measured against {MEASURED_AGAINST}: every tool it offers runs "
                "on this machine, and it talks to whatever provider it is pointed "
                "at rather than to one vendor, so there is nothing hosted to deny."
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
        }

        return Launch(
            env=env,
            argv=get_opencode_args(self.passthrough),
            caution=PROJECT_CONFIG_CAUTION,
        )
