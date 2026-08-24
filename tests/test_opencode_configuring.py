"""What offgrid writes into the directory OpenCode keeps, and what it leaves.

The other half of the split that `tests/test_opencode.py` covers: only what
offgrid never revises is written, because `configure` writes what is missing
and never overwrites — so a person who edited it keeps the edit, and nothing
derived from the profile can be left here to go stale.
"""

import json

import pytest

from offgrid.agents.opencode.configuring import PACKAGE, SCHEMA
from offgrid.shared.exceptions import AgentSettingsError
from tests.opencode_bindings import SETTINGS, bind, read_written


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def config_dir(tmp_path):
    """Where the agent keeps its own file, as its config derives it."""
    return tmp_path / "opencode"


@pytest.fixture
def configured(config_dir):
    """The agent, having written what it needed and did not have."""
    agent = bind()
    agent.configure()

    return agent


def test_the_provider_offgrid_writes_speaks_the_openai_protocol(configured, config_dir):
    # Without it the entry has no transport at all. Measured on opencode
    # 1.18.20, a provider absent from the published registry resolves against
    # this package, so naming it is stating what offgrid relies on rather than
    # what OpenCode would otherwise refuse.
    assert read_written(config_dir)["provider"]["offgrid"]["npm"] == PACKAGE


def test_the_provider_offgrid_writes_is_labelled(configured, config_dir):
    assert read_written(config_dir)["provider"]["offgrid"]["name"]


def test_what_offgrid_writes_says_which_schema_it_is(configured, config_dir):
    # More than the four things the ticket enumerates, and deliberate: the
    # file is meant to be edited, and this is what an editor completes and
    # validates it against.
    assert read_written(config_dir)["$schema"] == SCHEMA


def test_sharing_is_disabled_in_what_offgrid_writes(configured, config_dir):
    # A transcript leaving this machine is the promise `docs/decisions.md`
    # makes. The setting is an enum whose default the published schema does
    # not state, so writing the value is what makes the default irrelevant.
    assert read_written(config_dir)["share"] == "disabled"


def test_nothing_offgrid_writes_names_a_runtime(configured, config_dir):
    # The identifier OpenCode uses for a provider is an arbitrary label, so
    # making it a runtime's name would put a fact about runtimes inside an
    # agent adapter — and would deep-merge with an entry a person wrote for
    # that runtime themselves. The displayed label names none either.
    written = read_written(config_dir)

    assert set(written["provider"]) == {"offgrid"}
    assert "lmstudio" not in json.dumps(written).lower()


def test_nothing_offgrid_derives_is_written_where_it_could_go_stale(
    configured, config_dir
):
    # The address, the model and the window are rebuilt every run. Written
    # once into a file `configure` never overwrites, each would be silently
    # wrong the moment the profile changed — and a stale address hangs rather
    # than erroring.
    written = json.dumps(read_written(config_dir))

    assert "baseURL" not in written
    assert "models" not in written
    assert "127.0.0.1" not in written


def test_an_edited_configuration_is_left_as_a_person_left_it(config_dir):
    # Sharing is offgrid's default rather than offgrid's decision: somebody
    # who wants it back edits the file and keeps the edit.
    agent = bind()
    agent.configure()
    (config_dir / SETTINGS).write_text('{"share": "manual"}\n')

    agent.configure()

    assert read_written(config_dir)["share"] == "manual"


def test_a_configuration_that_cannot_be_written_says_what_stopped_it(
    tmp_path, monkeypatch
):
    # The command line reports offgrid's own errors and lets everything else
    # reach the terminal as a traceback, which is no use to whoever owns the
    # directory that would not take the file.
    in_the_way = tmp_path / "not-a-directory"
    in_the_way.write_text("")
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", in_the_way)

    with pytest.raises(AgentSettingsError) as refused:
        bind().configure()

    # The whole sentence, because a refusal naming neither the directory nor
    # what to do about it is a wall with no door in it.
    said = str(refused.value)
    assert str(in_the_way / "opencode") in said
    assert "cannot be written" in said
    assert "Fix what is there or what owns it, and run again." in said
