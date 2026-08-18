"""What Claude Code does with the directory it is run out of and the arguments.

What any agent owes is stated once, in `tests/test_agent_conformance.py`. What
is here is Claude Code's own: which environment variables carry the model and
the window it is served at, the arguments offgrid adds, the argument a person
can add that stops the settings being loaded at all, and what its settings file
is read as when it holds something nobody can act on.
"""

import json

import pytest

from offgrid.agents import create_agent_config
from offgrid.agents.claude_code import prepare
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsStatus
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import AgentSettingsError

HOST = "127.0.0.1:1234"


def _config(**said):
    """The config the registry would build, from what a profile said."""
    return create_agent_config({"name": "claude-code"} | said, runtime_host=HOST)


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def config_dir(tmp_path):
    """Where the agent keeps its own files, as its config derives it."""
    made = tmp_path / "claude-code"
    made.mkdir()

    return made


@pytest.fixture
def agent():
    return prepare(_config(), ())


@pytest.fixture
def started_with():
    """Answer with an agent bound to the arguments a run would hand on."""

    def bind(*passthrough):
        return prepare(_config(), passthrough)

    return bind


@pytest.fixture
def launch(agent):
    model = Model(
        identifier="qwen/qwen3.6-35b-a3b", context_ceiling=262144, context_window=212224
    )
    return agent.plan(model)


def _settings(config_dir):
    return json.loads((config_dir / "settings.json").read_text())


def test_claude_code_speaks_the_anthropic_dialect(agent):
    assert agent.dialect is Dialect.ANTHROPIC


def test_claude_code_will_not_start_in_a_window_under_25k(agent):
    # Its system prompt and tool definitions do not fit below this, and what
    # is on the other side is a failure at startup rather than a cramped
    # session. The number is written out here rather than read from the
    # source, so that changing the source is a decision this test asks about.
    assert agent.context_floor == 25_000


def test_the_agent_is_pointed_at_the_local_server(launch):
    assert launch.env["ANTHROPIC_BASE_URL"] == f"http://{HOST}"


def test_the_agent_is_given_a_token_the_local_server_ignores(launch):
    # Claude Code will not start without one, and the local server never looks
    # at it. Nothing else in a launch fails this quietly: no token is a refusal
    # from the agent, before the model that was just held is ever asked.
    assert launch.env["ANTHROPIC_AUTH_TOKEN"]


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


def test_the_config_directory_is_the_one_the_agent_derives(launch, config_dir):
    assert launch.env["CLAUDE_CONFIG_DIR"] == str(config_dir)


def test_no_mcp_servers_are_loaded(launch):
    assert "--strict-mcp-config" in launch.argv


def test_volatile_prompt_sections_stay_out_of_the_cached_prefix(launch):
    assert "--exclude-dynamic-system-prompt-sections" in launch.argv


def test_a_model_whose_window_is_unstated_is_not_sized_from_its_ceiling(agent):
    # The ceiling is what the model could be served at, not what it is being
    # served at, and compacting against a window nothing is serving is the
    # truncation that reading the window exists to avoid.
    unstated_window = Model(
        identifier="a/b", context_ceiling=262144, context_window=None
    )

    launch = agent.plan(unstated_window)

    assert "CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in launch.env
    assert launch.caution and "262144" not in launch.caution


def test_a_model_with_no_stated_context_is_said_to_compact_too_late(agent):
    # Nothing to size compaction to and nothing to guess with: what is left is
    # saying so, since the person meets it as a truncated prefix otherwise.
    unstated = Model(identifier="a/b", context_ceiling=None, context_window=None)

    launch = agent.plan(unstated)

    assert "CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in launch.env
    assert launch.caution and "no window" in launch.caution
    assert "/compact" in launch.caution


def test_a_window_under_the_one_that_is_honoured_is_not_asked_for(agent):
    # Claude Code raises anything under 100,000 to 100,000, so a run served at
    # 32,768 that asked for it would compact at 100k while the runtime
    # truncated the prefix at 32k. What a person reads names both numbers,
    # because neither of them is guessable from the other.
    served_small = Model(identifier="a/b", context_ceiling=262144, context_window=32768)

    launch = agent.plan(served_small)

    assert "CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in launch.env
    assert "32768" in launch.caution
    assert "100000" in launch.caution
    assert "/compact" in launch.caution


@pytest.mark.parametrize("window", [None, 1, 8192, 32768, 99_999, 100_000, 262144])
def test_a_window_is_either_asked_for_or_spoken_about(agent, window):
    # The pair either way round is the failure: a window set beside a sentence
    # saying none was sends someone to /compact for nothing, and a window
    # unset with nothing said is the truncation this exists to prevent. One
    # decision, so the two halves are the same answer read twice.
    launch = agent.plan(
        Model(identifier="a/b", context_ceiling=262144, context_window=window)
    )

    asked_for = "CLAUDE_CODE_AUTO_COMPACT_WINDOW" in launch.env

    assert asked_for is (launch.caution is None)
    assert asked_for is ("CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in launch.dropped)


def test_the_smallest_honoured_window_is_asked_for(agent):
    # The boundary itself: at 100,000 the number asked for is the number
    # served, so it is set rather than withheld, and nothing is said.
    served_at_the_floor = Model(
        identifier="a/b", context_ceiling=262144, context_window=100_000
    )

    launch = agent.plan(served_at_the_floor)

    assert launch.env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "100000"
    assert launch.caution is None


def test_the_configuration_denies_the_search_that_cannot_work(agent, config_dir):
    # WebSearch runs on Anthropic's servers, so against a local model the
    # model invents a result and Claude Code returns it without an error.
    agent.configure()

    assert "WebSearch" in _settings(config_dir)["permissions"]["deny"]


def test_no_mcp_servers_are_enabled_in_the_configuration(agent, config_dir):
    agent.configure()

    assert _settings(config_dir)["enableAllProjectMcpServers"] is False


def test_the_configuration_tells_the_agent_it_cannot_search(agent, config_dir):
    # Discovering the wall by calling the tool costs a turn, and locally a
    # turn is tens of seconds.
    agent.configure()
    notes = (config_dir / "CLAUDE.md").read_text()

    assert "WebSearch" in notes
    assert "WebFetch" in notes


def test_a_configuration_that_cannot_be_written_says_what_stopped_it(
    tmp_path, monkeypatch
):
    # The command line reports offgrid's own errors and lets everything else
    # reach the terminal as a traceback, which is no use to whoever owns the
    # directory that would not take the file.
    in_the_way = tmp_path / "not-a-directory"
    in_the_way.write_text("")
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", in_the_way)

    with pytest.raises(AgentSettingsError, match="cannot be written"):
        prepare(_config(), ()).configure()


def test_what_the_agent_writes_for_itself_denies_the_tool_rather_than_lacking_one(
    agent,
):
    # The suite asks that its own default satisfies its own guard, which an
    # adapter claiming to offer no hosted tool would also pass. Claude Code
    # offers one, measured against claude 2.1.231, so `DENIED` is the only
    # answer that is true of it.
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.DENIED


def test_settings_that_would_let_the_agent_search_read_as_permitted(agent, config_dir):
    # The file is hand-editable, and an edit that drops the deny brings back
    # the invented answers it was written to prevent.
    (config_dir / "settings.json").write_text('{"theme": "mine"}')

    found = agent.read_hosted_tools()

    assert found.status is HostedToolsStatus.PERMITTED
    assert "WebSearch" in found.detail
    assert "permissions.deny" in found.remedy


def test_settings_nobody_has_written_yet_are_not_called_permitted(agent):
    # `setup` writes a profile and no agent configuration, so this is every
    # machine before its first run. Nothing is wrong, and nothing is denied.
    found = agent.read_hosted_tools()

    assert found.status is HostedToolsStatus.UNWRITTEN
    assert "offgrid run" in found.remedy


def test_an_argument_that_drops_the_settings_reads_as_permitted(started_with):
    # Measured against claude 2.1.231: a --setting-sources list without `user`
    # never loads the file offgrid wrote, and WebSearch is offered again. The
    # file is correct here — the argument is what makes it beside the point.
    agent = started_with("--setting-sources", "project,local")
    agent.configure()

    found = agent.read_hosted_tools()

    assert found.status is HostedToolsStatus.PERMITTED
    assert "--setting-sources project,local" in found.detail
    assert found.remedy == "Add `user` to the list, or drop the argument."


def test_the_joined_spelling_of_that_argument_is_read_too(started_with):
    # Claude Code takes a value either way round, and both were measured to
    # drop the deny, so reading only one of them misses half the cases.
    agent = started_with("--setting-sources=project,local")
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.PERMITTED


def test_the_last_of_two_such_arguments_is_the_one_that_counts(started_with):
    # Claude Code takes the last, measured both ways round: naming `user`
    # first and dropping it after leaves WebSearch offered, so reading the
    # first argument passes exactly the line that defeats it.
    agent = started_with(
        "--setting-sources", "user", "--setting-sources", "project,local"
    )
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.PERMITTED


def test_a_later_argument_naming_it_again_reads_as_denied(started_with):
    # The same rule from the other side: the last one names `user`, so the
    # settings load and calling this permitted would cost a run never at risk.
    agent = started_with(
        "--setting-sources", "project,local", "--setting-sources", "user"
    )
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.DENIED


def test_sources_that_still_name_the_one_offgrid_wrote_read_as_denied(started_with):
    # The argument is not the problem — leaving out `user` is. Spaced, and
    # named second, so the entry that has to match carries the space.
    agent = started_with("--setting-sources", "project, user")
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.DENIED


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
def test_arguments_measured_to_leave_the_deny_standing_read_as_denied(
    started_with, argument
):
    # Regression guards, not slices. The first three read as though they undo
    # the deny and do not: against claude 2.1.231 the tool list is built with
    # `deny` already applied, so nothing that turns a permission check off or
    # adds an allow puts WebSearch back. Calling them permitted would cost
    # someone a run for no gain. The fourth is the flag as a value rather than
    # as an argument, which reaches the model as text and configures nothing.
    agent = started_with(*argument)
    agent.configure()

    assert agent.read_hosted_tools().status is HostedToolsStatus.DENIED


def test_settings_that_are_not_readable_json_are_refused(agent, config_dir):
    # Not an answer about hosted tools: the file is there and says nothing
    # either way, which is a fault to fix rather than a state to report.
    (config_dir / "settings.json").write_text('{"permissions": ')

    with pytest.raises(AgentSettingsError, match="not readable as JSON"):
        agent.read_hosted_tools()


@pytest.mark.parametrize(
    "written",
    [
        '{"permissions": {"deny": "WebSearch"}}',
        '{"permissions": ["deny"]}',
        '["permissions"]',
    ],
    ids=["deny is a word", "permissions is a list", "the file is a list"],
)
def test_settings_shaped_so_nothing_denies_anything_read_as_permitted(
    agent, config_dir, written
):
    # Regression guards, not slices: they pass as written. A settings file is
    # typed by hand into a schema nobody memorises, and each of these is a
    # shape the agent itself ignores — so reading a deny out of one and
    # calling the run safe is the invented answer the guard exists to stop.
    (config_dir / "settings.json").write_text(written)

    assert agent.read_hosted_tools().status is HostedToolsStatus.PERMITTED


def test_settings_that_are_not_text_are_not_called_bad_json(agent, config_dir):
    # A file whose bytes are not text never reached the parser, so naming
    # JSON sends someone looking for a bracket in a file that has none.
    (config_dir / "settings.json").write_bytes(b'{"permissions": \xff}')

    with pytest.raises(AgentSettingsError, match="cannot be read") as refused:
        agent.read_hosted_tools()

    assert "JSON" not in str(refused.value)


def test_settings_that_are_there_and_unreadable_are_not_called_missing(
    agent, config_dir
):
    # "It is not there" sends someone to write a file that is already there.
    # What stopped the read is what they need, whatever it was.
    (config_dir / "settings.json").mkdir()

    with pytest.raises(AgentSettingsError, match="cannot be read") as refused:
        agent.read_hosted_tools()

    assert "is not there" not in str(refused.value)
