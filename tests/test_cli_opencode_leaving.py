"""What a command says about an OpenCode configuration that could share.

The seam is the command: what a person reads, and whether the run starts. This
is the gap issue #162 was filed for — `configure` leaves an edited file exactly
as it found it, correctly, so the file deciding whether a transcript leaves was
written once and never read, and a person who turned sharing back on got a
clean report and a run that went ahead.

`tests/test_cli_opencode.py` is the rest of what a command does with this
adapter, and this is its own module so that neither grows past the length a
file is kept to.
"""

from typer.testing import CliRunner

from offgrid.cli import app
from tests.launches import record_launch
from tests.opencode_bindings import name_opencode, write_configuration

runner = CliRunner()


def test_doctor_says_a_hand_edited_configuration_could_share_a_transcript(here):
    # Sharing turned back on by hand. The report names the file and the value
    # to set, because `doctor` exists to save someone the load a run costs and
    # saying only that something is permitted sends them to make it anyway.
    name_opencode(here)
    write_configuration(here, '{"share": "manual"}')

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "  transcript sharing  permitted" in result.stderr
    assert "opencode.json" in result.stderr
    assert "disabled" in result.stderr


def test_doctor_says_a_configuration_stating_no_sharing_settles_nothing(here):
    # A file edited down to keys offgrid never wrote is one `configure` will
    # not write into, so nothing but this reading can say the promise about
    # transcripts is not being kept — and it has to say what to type, since no
    # run will type it for them.
    name_opencode(here)
    write_configuration(here, '{"theme": "mine"}')

    result = runner.invoke(app, ["doctor"])

    assert "  transcript sharing  unwritten" in result.stderr
    assert "will not write into it" in result.stderr
    assert '"share": "disabled"' in result.stderr


def test_doctor_says_a_value_back_the_way_the_file_spells_it(here):
    # A person is being sent to a JSON file to look at what they set, so the
    # report says `false` and not `False`: one of those is in the file and the
    # other is Python talking about it. Any value but `disabled` is refused,
    # including one OpenCode would not accept either.
    name_opencode(here)
    write_configuration(here, '{"share": false}')

    result = runner.invoke(app, ["doctor"])

    assert "  transcript sharing  permitted" in result.stderr
    assert "to false," in result.stderr
    assert "False" not in result.stderr


def test_run_refuses_a_configuration_that_could_share_a_transcript(here, monkeypatch):
    # Before the load, which is why the reading sits where the dialect check
    # sits: a refusal after it costs the tens of seconds nobody gets back.
    name_opencode(here)
    write_configuration(here, '{"share": "auto"}')
    started = record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "transcript sharing" in result.stderr
    assert not started


def test_run_leaves_a_configuration_it_refuses_on_exactly_as_it_was(here, monkeypatch):
    # The refusal is the point and the file is the person's. A run that fixed
    # it for them would turn something they can act on into a silent rewrite.
    name_opencode(here)
    edited = '{"share": "manual"}'
    write_configuration(here, edited)
    record_launch(monkeypatch)

    runner.invoke(app, ["run"])

    assert (here / "opencode" / "opencode.json").read_text() == edited
