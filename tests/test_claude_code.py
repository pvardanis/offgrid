import pytest

from offgrid.agents.claude_code import dialect, plan
from offgrid.dialect import Dialect
from offgrid.model import Model

HOST = "127.0.0.1:1234"


@pytest.fixture
def launch(tmp_path):
    model = Model(identifier="qwen/qwen3.6-35b-a3b", context_limit=212224)
    return plan(model, host=HOST, config_dir=tmp_path, token="lmstudio")


def test_claude_code_speaks_the_anthropic_dialect():
    assert dialect() is Dialect.ANTHROPIC


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


def test_the_config_directory_is_offgrids_own(launch, tmp_path):
    assert launch.env["CLAUDE_CONFIG_DIR"] == str(tmp_path)


def test_no_mcp_servers_are_loaded(launch):
    assert "--strict-mcp-config" in launch.argv


def test_volatile_prompt_sections_stay_out_of_the_cached_prefix(launch):
    assert "--exclude-dynamic-system-prompt-sections" in launch.argv


def test_arguments_are_passed_through_to_the_agent(tmp_path):
    model = Model(identifier="a/b", context_limit=8192)
    launch = plan(
        model, host=HOST, config_dir=tmp_path, token="t", passthrough=["-p", "hi"]
    )
    assert launch.argv[-2:] == ["-p", "hi"]


def test_a_model_with_no_stated_context_gets_a_workable_default(tmp_path):
    unstated = Model(identifier="a/b", context_limit=0)
    launch = plan(unstated, host=HOST, config_dir=tmp_path, token="t")
    assert int(launch.env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"]) > 0


def test_the_profile_directory_denies_the_search_that_cannot_work(tmp_path):
    # WebSearch runs on Anthropic's servers, so against a local model the
    # model invents a result and Claude Code returns it without an error.
    import json

    from offgrid.agents.claude_code import prepare

    prepare(tmp_path)
    settings = json.loads((tmp_path / "settings.json").read_text())
    assert "WebSearch" in settings["permissions"]["deny"]


def test_no_mcp_servers_are_enabled_in_the_profile(tmp_path):
    import json

    from offgrid.agents.claude_code import prepare

    prepare(tmp_path)
    settings = json.loads((tmp_path / "settings.json").read_text())
    assert settings["enableAllProjectMcpServers"] is False


def test_an_existing_profile_is_left_alone(tmp_path):
    from offgrid.agents.claude_code import prepare

    settings = tmp_path / "settings.json"
    tmp_path.mkdir(exist_ok=True)
    kept = '{"theme": "mine", "permissions": {"deny": ["WebSearch"]}}'
    settings.write_text(kept)

    prepare(tmp_path)
    assert settings.read_text() == kept


def test_the_profile_tells_the_agent_it_cannot_search(tmp_path):
    # Discovering the wall by calling the tool costs a turn, and locally a
    # turn is tens of seconds.
    from offgrid.agents.claude_code import prepare

    prepare(tmp_path)
    notes = (tmp_path / "CLAUDE.md").read_text()

    assert "WebSearch" in notes
    assert "WebFetch" in notes


def test_notes_already_written_are_left_alone(tmp_path):
    from offgrid.agents.claude_code import prepare

    notes = tmp_path / "CLAUDE.md"
    tmp_path.mkdir(exist_ok=True)
    notes.write_text("# mine\n")

    prepare(tmp_path)
    assert notes.read_text() == "# mine\n"


def test_a_profile_that_would_let_the_agent_search_is_refused(tmp_path):
    # The file is hand-editable, and an edit that drops the deny brings back
    # the invented answers it was written to prevent.
    from offgrid.agents.claude_code import prepare
    from offgrid.exceptions import AgentSettingsError

    settings = tmp_path / "settings.json"
    tmp_path.mkdir(exist_ok=True)
    settings.write_text('{"theme": "mine"}')

    with pytest.raises(AgentSettingsError, match="WebSearch"):
        prepare(tmp_path)


def test_a_profile_that_is_not_readable_json_is_refused(tmp_path):
    from offgrid.agents.claude_code import prepare
    from offgrid.exceptions import AgentSettingsError

    settings = tmp_path / "settings.json"
    tmp_path.mkdir(exist_ok=True)
    settings.write_text('{"permissions": ')

    with pytest.raises(AgentSettingsError, match=r"settings\.json"):
        prepare(tmp_path)
