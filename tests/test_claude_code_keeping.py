"""What Claude Code keeps of its settings, and what it then says about them.

This adapter reads its own file back, so the two calls have to agree about
what "nothing is there" means. Where they disagree the disagreement is silent
and circular: `configure` keeps a file because it holds something, the guard
calls the same file empty, and the remedy it offers is the command that just
refused.
"""

import pytest

from offgrid.agents.claude_code import prepare
from offgrid.agents.claude_code.config import ClaudeCodeConfig
from offgrid.domain.running.hosted_tools import HostedToolsStatus
from tests.claude_code_under_test import HOST

SETTINGS = "settings.json"


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def config_dir(tmp_path):
    """Where the agent keeps its own files, as its config derives it."""
    return tmp_path / "claude-code"


def bind():
    """The adapter, run out of the directory the test owns."""
    return prepare(ClaudeCodeConfig(runtime_host=HOST), ())


def test_settings_holding_null_are_kept_and_reported_as_a_person_can_act_on(
    config_dir,
):
    # `null` parses, so it is an edit and `configure` keeps it — and a guard
    # reading absence off the parsed value would call the file empty, because
    # `null` is also what "nothing" is spelled as there.
    #
    # What that costs is the whole of the remedy. `UNWRITTEN` says to run
    # `offgrid run`, which is what is running: it calls `configure`, which
    # keeps the file, and refuses again on the same sentence. The answer a
    # person can act on is the one that names deleting it.
    config_dir.mkdir(parents=True)
    (config_dir / SETTINGS).write_text("null\n")
    agent = bind()

    agent.configure()

    found = agent.read_hosted_tools()
    assert (config_dir / SETTINGS).read_text() == "null\n"
    assert found.status is HostedToolsStatus.PERMITTED
    assert found.remedy and "delete the file" in found.remedy


def test_emptied_settings_are_written_again_and_then_deny_websearch(config_dir):
    # The other side of the same agreement: an empty file holds no edit, so
    # both calls treat it as nothing there — `configure` writes the settings
    # into it, and the guard reads back the deny that was just written rather
    # than reporting the file it no longer describes.
    agent = bind()
    agent.configure()
    (config_dir / SETTINGS).write_text("")

    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.DENIED
