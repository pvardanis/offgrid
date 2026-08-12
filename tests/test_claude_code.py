import json

import pytest

from offgrid.agents.claude_code import prepare
from offgrid.dialect import Dialect
from offgrid.exceptions import AgentSettingsError
from offgrid.model import Model

HOST = "127.0.0.1:1234"


@pytest.fixture
def agent(tmp_path):
    return prepare(tmp_path)


@pytest.fixture
def launch(agent):
    model = Model(identifier="qwen/qwen3.6-35b-a3b", context_limit=212224)
    return agent.plan(model, host=HOST, token="lmstudio", passthrough=[])


def _settings(config_dir):
    return json.loads((config_dir / "settings.json").read_text())


def test_claude_code_speaks_the_anthropic_dialect(agent):
    assert agent.dialect is Dialect.ANTHROPIC


def test_the_agent_is_pointed_at_the_local_server(launch):
    assert launch.env["ANTHROPIC_BASE_URL"] == f"http://{HOST}"


def test_every_model_tier_resolves_to_the_local_model(launch):
    tiers = [
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    ]
    assert {launch.env[tier] for tier in tiers} == {"qwen/qwen3.6-35b-a3b"}


def test_compaction_is_sized_from_the_model_being_served(launch):
    # Compacting early costs a summarization call and a cold reprefill;
    # compacting late truncates the prefix. Both are expensive locally.
    assert launch.env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "212224"


def test_thinking_is_off_because_it_is_paid_for_at_decode_speed(launch):
    assert launch.env["MAX_THINKING_TOKENS"] == "0"


def test_the_config_directory_is_the_one_the_agent_was_bound_to(launch, tmp_path):
    assert launch.env["CLAUDE_CONFIG_DIR"] == str(tmp_path)


def test_no_mcp_servers_are_loaded(launch):
    assert "--strict-mcp-config" in launch.argv


def test_volatile_prompt_sections_stay_out_of_the_cached_prefix(launch):
    assert "--exclude-dynamic-system-prompt-sections" in launch.argv


def test_arguments_are_passed_through_to_the_agent(agent):
    model = Model(identifier="a/b", context_limit=8192)
    launch = agent.plan(model, host=HOST, token="t", passthrough=["-p", "hi"])

    assert launch.argv[-2:] == ["-p", "hi"]


def test_a_model_with_no_stated_context_gets_a_workable_default(agent):
    unstated = Model(identifier="a/b", context_limit=0)
    launch = agent.plan(unstated, host=HOST, token="t", passthrough=[])

    assert int(launch.env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"]) > 0


def test_planning_a_launch_writes_nothing(agent, tmp_path):
    # An environment and an argument list can be shown before anything runs,
    # which is only true while building one changes nothing on disk.
    model = Model(identifier="a/b", context_limit=8192)
    agent.plan(model, host=HOST, token="t", passthrough=[])

    assert list(tmp_path.iterdir()) == []


def test_the_configuration_denies_the_search_that_cannot_work(agent, tmp_path):
    # WebSearch runs on Anthropic's servers, so against a local model the
    # model invents a result and Claude Code returns it without an error.
    agent.configure()

    assert "WebSearch" in _settings(tmp_path)["permissions"]["deny"]


def test_no_mcp_servers_are_enabled_in_the_configuration(agent, tmp_path):
    agent.configure()

    assert _settings(tmp_path)["enableAllProjectMcpServers"] is False


def test_the_configuration_tells_the_agent_it_cannot_search(agent, tmp_path):
    # Discovering the wall by calling the tool costs a turn, and locally a
    # turn is tens of seconds.
    agent.configure()
    notes = (tmp_path / "CLAUDE.md").read_text()

    assert "WebSearch" in notes
    assert "WebFetch" in notes


def test_settings_already_there_are_left_alone(agent, tmp_path):
    settings = tmp_path / "settings.json"
    kept = '{"theme": "mine", "permissions": {"deny": ["WebSearch"]}}'
    settings.write_text(kept)

    agent.configure()

    assert settings.read_text() == kept


def test_notes_already_written_are_left_alone(agent, tmp_path):
    notes = tmp_path / "CLAUDE.md"
    notes.write_text("# mine\n")

    agent.configure()

    assert notes.read_text() == "# mine\n"


def test_configuring_twice_changes_nothing_the_second_time(agent, tmp_path):
    agent.configure()
    written = {path.name: path.read_text() for path in tmp_path.iterdir()}

    agent.configure()

    assert {path.name: path.read_text() for path in tmp_path.iterdir()} == written


def test_what_the_agent_writes_for_itself_passes_its_own_guard(agent):
    agent.configure()

    agent.require_hosted_tools_denied()


def test_configuring_does_not_refuse_settings_the_guard_would(agent, tmp_path):
    # Two jobs, and only one of them is allowed to stop a run: settings that
    # would let the agent search are still an edit worth keeping.
    permitting = '{"theme": "mine"}'
    (tmp_path / "settings.json").write_text(permitting)

    agent.configure()

    assert (tmp_path / "settings.json").read_text() == permitting


def test_settings_that_would_let_the_agent_search_are_refused(agent, tmp_path):
    # The file is hand-editable, and an edit that drops the deny brings back
    # the invented answers it was written to prevent.
    (tmp_path / "settings.json").write_text('{"theme": "mine"}')

    with pytest.raises(AgentSettingsError, match="WebSearch"):
        agent.require_hosted_tools_denied()


def test_settings_that_are_not_readable_json_are_refused(agent, tmp_path):
    (tmp_path / "settings.json").write_text('{"permissions": ')

    with pytest.raises(AgentSettingsError, match=r"settings\.json"):
        agent.require_hosted_tools_denied()


def test_settings_that_are_not_there_at_all_are_refused(agent, tmp_path):
    # Nothing denies WebSearch, which is what the guard is asked. Saying the
    # file is missing sends someone to `configure` rather than to an editor.
    with pytest.raises(AgentSettingsError, match="offgrid run"):
        agent.require_hosted_tools_denied()
