"""What `offgrid doctor` says about where a conversation started here is kept.

The finding a person otherwise meets as a missing session: `claude --resume
<id>` in an ordinary terminal answers "No conversation found with session ID"
for a run offgrid started minutes earlier, because a run is its own
installation and the transcript is where offgrid put it. `docs/decisions.md`
says why that stays, under "A conversation started here is resumed here", and
this is where a person is told.
"""

from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.domain.running.conversations import STARTED_ON_ITS_OWN
from tests.commands import unwrapped
from tests.opencode_bindings import name_opencode

runner = CliRunner()


def test_doctor_says_where_a_conversation_is_kept_and_how_to_open_one(here):
    # Both halves. A directory is what somebody already had: what they are
    # missing is that the agent started on its own reads a different one, and
    # the command that reads this one.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert f"conversations\n  {here / 'claude-code'}\n" in result.stderr
    assert "offgrid run -- --resume" in result.stderr
    # The finding, not only the remedy. It is the domain's sentence rather than
    # the adapter's, so a report that said the adapter's half alone would leave
    # a person with a command and no reason to think they needed it.
    assert STARTED_ON_ITS_OWN in unwrapped(result.stderr)


def test_doctor_says_it_on_a_machine_that_has_never_run_the_agent(here):
    # It is answered out of what a run would point the agent at rather than
    # out of anything on disk, so there is no first run to have made before
    # the report can say it — and nothing is created by asking.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert f"conversations\n  {here / 'claude-code'}" in result.stderr
    assert not (here / "claude-code").exists()


def test_doctor_says_it_for_the_other_agent_too(here):
    # No branch: every agent offgrid runs is run out of a directory of
    # offgrid's, so a line one of them did not get would leave that person with
    # the silence this command exists to break. The store rather than the
    # directory beside it, because that is what `XDG_DATA_HOME` moves.
    name_opencode(here)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert f"conversations\n  {here / 'opencode' / 'store'}\n" in result.stderr
    assert "offgrid run -- run --continue" in result.stderr
