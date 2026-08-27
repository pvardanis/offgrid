"""What `offgrid doctor` says about what a run could send off this machine.

A hosted tool runs on its vendor's servers, so against a model held here there
is nothing to run it; a transcript that leaves goes to the same place while the
run works exactly as asked. `doctor` reports what `run` refuses, and this is
where what it reports is read back.
"""

from typer.testing import CliRunner

from offgrid.cli import app

runner = CliRunner()


def test_doctor_says_nothing_is_written_before_a_first_run(here):
    # `setup` writes a profile and no agent configuration, so on a machine
    # that has never run the agent there is nothing to deny with. Saying so
    # is not a fault: it is what a run would fix on its way past.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "unwritten" in result.stderr


def test_doctor_says_a_hand_edited_settings_file_permits_the_search(here):
    # The machine this command was missing: the deny taken out by hand used
    # to get four green lines here and a refusal from `run`.
    runner.invoke(app, ["setup"])
    config = here / "claude-code"
    config.mkdir()
    (config / "settings.json").write_text('{"theme": "mine"}')

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "permitted" in result.stderr


def test_doctor_says_what_to_change_when_a_tool_can_be_reached(here):
    # `doctor` exists to save someone the load a run costs. Saying only that
    # something is permitted sends them to make the run anyway to find out
    # which file and what to type.
    runner.invoke(app, ["setup"])
    config = here / "claude-code"
    config.mkdir()
    (config / "settings.json").write_text('{"theme": "mine"}')

    result = runner.invoke(app, ["doctor"])

    assert "settings.json" in result.stderr
    assert "permissions.deny" in result.stderr


def test_doctor_says_no_more_than_the_state_when_nothing_can_be_reached(here):
    # Nothing to act on, so nothing to read: the four lines beside it are
    # what someone came for.
    runner.invoke(app, ["setup"])
    config = here / "claude-code"
    config.mkdir()
    (config / "settings.json").write_text('{"permissions": {"deny": ["WebSearch"]}}')

    result = runner.invoke(app, ["doctor"])

    assert "          hosted tools: denied\n" in result.stderr
    assert "settings.json" not in result.stderr


def test_doctor_reports_settings_it_cannot_read_rather_than_crashing(here):
    # A file that is there and unreadable is a fault rather than an answer
    # about hosted tools, and offgrid's own errors are reported: a traceback
    # is what everything else gets.
    runner.invoke(app, ["setup"])
    config = here / "claude-code"
    config.mkdir()
    (config / "settings.json").write_text('{"permissions": ')

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "not readable as JSON" in result.stderr


def test_doctor_says_an_argument_would_send_the_session_elsewhere(here):
    # `doctor` binds with no arguments, so the one thing it can honestly say
    # about the command line is what it says with none: nothing on it asks for
    # a session somewhere else. The line is still there, because a person
    # reading the report is owed the subject as well as the state.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "          transcript sharing: denied\n" in result.stderr


def test_doctor_writes_no_configuration(here):
    # It reports what a run would do. Reaching the registry to ask the agent
    # what it speaks binds a directory and nothing more.
    runner.invoke(app, ["setup"])

    runner.invoke(app, ["doctor"])

    assert not (here / "claude-code").exists()
