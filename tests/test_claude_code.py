import json

import pytest

from offgrid.agents.claude_code import prepare
from offgrid.agents.claude_code.launching import FALLBACK_CONTEXT
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

    assert launch.env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == str(FALLBACK_CONTEXT)


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


def test_a_configuration_that_cannot_be_written_says_what_stopped_it(tmp_path):
    # The command line reports offgrid's own errors and lets everything else
    # reach the terminal as a traceback, which is no use to whoever owns the
    # directory that would not take the file.
    in_the_way = tmp_path / "not-a-directory"
    in_the_way.write_text("")

    with pytest.raises(AgentSettingsError, match="cannot be written"):
        prepare(in_the_way / "claude-code").configure()


def test_what_the_agent_writes_for_itself_passes_its_own_guard(agent):
    agent.configure()

    agent.require_hosted_tools_denied([])


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
        agent.require_hosted_tools_denied([])


def test_arguments_that_stop_the_settings_being_read_are_refused(agent):
    # Measured against claude 2.1.231: a --setting-sources list without `user`
    # never loads the file offgrid wrote, and WebSearch is offered again.
    agent.configure()

    with pytest.raises(AgentSettingsError) as refused:
        agent.require_hosted_tools_denied(["--setting-sources", "project,local"])

    # What a person can act on: which argument, what it cost them, what to
    # type instead. A message worn down to the flag name says none of it.
    complaint = str(refused.value)
    assert "--setting-sources project,local" in complaint
    assert "WebSearch" in complaint
    assert "Add `user` to the list, or drop the argument." in complaint


def test_the_joined_spelling_of_that_argument_is_refused_too(agent):
    # Claude Code takes a value either way round, and both were measured to
    # drop the deny, so reading only one of them refuses half the cases.
    agent.configure()

    with pytest.raises(AgentSettingsError, match="--setting-sources"):
        agent.require_hosted_tools_denied(["--setting-sources=project,local"])


def test_the_last_of_two_such_arguments_is_the_one_that_counts(agent):
    # Claude Code takes the last, measured both ways round: naming `user`
    # first and dropping it after leaves WebSearch offered, so a guard reading
    # the first argument passes exactly the line that defeats it.
    agent.configure()

    with pytest.raises(AgentSettingsError, match="--setting-sources"):
        agent.require_hosted_tools_denied(
            ["--setting-sources", "user", "--setting-sources", "project,local"]
        )


def test_a_later_argument_naming_it_again_is_allowed(agent):
    # The same rule from the other side: the last one names `user`, so the
    # settings load and refusing would cost a run that was never at risk.
    agent.configure()

    agent.require_hosted_tools_denied(
        ["--setting-sources", "project,local", "--setting-sources", "user"]
    )


def test_sources_that_still_name_the_one_offgrid_wrote_are_allowed(agent):
    # The argument is not the problem — leaving out `user` is. Narrowing the
    # sources while keeping that one still loads the deny. Spaced, and named
    # second, so the entry that has to match is the one carrying the space.
    agent.configure()

    agent.require_hosted_tools_denied(["--setting-sources", "project, user"])


@pytest.mark.parametrize(
    "argument",
    [
        ["--dangerously-skip-permissions"],
        ["--permission-mode", "bypassPermissions"],
        ["--allowedTools", "WebSearch"],
        ["-p", "run it with --setting-sources=project"],
    ],
    ids=["skip permissions", "bypass mode", "allow the tool", "a prompt naming it"],
)
def test_arguments_measured_to_leave_the_deny_standing_are_allowed(agent, argument):
    # Regression guards, not slices. The first three read as though they undo
    # the deny and do not: against claude 2.1.231 the tool list is built with
    # `deny` already applied, so nothing that turns a permission check off or
    # adds an allow puts WebSearch back. Refusing them would cost someone a
    # run for no gain. The fourth is the flag as a value rather than as an
    # argument, which reaches the model as text and configures nothing.
    agent.configure()

    agent.require_hosted_tools_denied(argument)


def test_settings_that_are_not_readable_json_are_refused(agent, tmp_path):
    (tmp_path / "settings.json").write_text('{"permissions": ')

    with pytest.raises(AgentSettingsError, match="not readable as JSON"):
        agent.require_hosted_tools_denied([])


@pytest.mark.parametrize(
    "written",
    [
        '{"permissions": {"deny": "WebSearch"}}',
        '{"permissions": ["deny"]}',
        '["permissions"]',
    ],
    ids=["deny is a word", "permissions is a list", "the file is a list"],
)
def test_settings_shaped_so_nothing_denies_anything_are_refused(
    agent, tmp_path, written
):
    # Regression guards, not slices: they pass as written. A settings file is
    # typed by hand into a schema nobody memorises, and each of these is a
    # shape the agent itself ignores — so reading a deny out of one and
    # calling the run safe is the invented answer the guard exists to stop.
    (tmp_path / "settings.json").write_text(written)

    with pytest.raises(AgentSettingsError, match="does not deny WebSearch"):
        agent.require_hosted_tools_denied([])


def test_settings_that_are_not_there_at_all_are_refused(agent, tmp_path):
    # Nothing denies WebSearch, which is what the guard is asked. Saying the
    # file is missing sends someone to `configure` rather than to an editor.
    with pytest.raises(AgentSettingsError, match="offgrid run"):
        agent.require_hosted_tools_denied([])


def test_settings_that_are_not_text_are_not_called_bad_json(agent, tmp_path):
    # A file whose bytes are not text never reached the parser, so naming
    # JSON sends someone looking for a bracket in a file that has none.
    (tmp_path / "settings.json").write_bytes(b'{"permissions": \xff}')

    with pytest.raises(AgentSettingsError, match="cannot be read") as refused:
        agent.require_hosted_tools_denied([])

    assert "JSON" not in str(refused.value)


def test_settings_that_are_there_and_unreadable_are_not_called_missing(agent, tmp_path):
    # "It is not there" sends someone to write a file that is already there.
    # What stopped the read is what they need, whatever it was.
    (tmp_path / "settings.json").mkdir()

    with pytest.raises(AgentSettingsError, match="cannot be read") as refused:
        agent.require_hosted_tools_denied([])

    assert "is not there" not in str(refused.value)
