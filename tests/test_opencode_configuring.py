"""What offgrid writes into a fresh OpenCode directory.

The other half of the split that `tests/test_opencode.py` covers: only what
offgrid never revises is written, so nothing derived from the profile can be
left here to go stale. What happens to a file that is already there is beside
this, in `tests/test_opencode_keeping.py`.
"""

import json

import pytest

from tests.opencode_bindings import RUNTIME_SPELLINGS, bind, read_written


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
    # Measured on opencode 1.18.20, a provider absent from the published
    # registry resolves against this package anyway, so naming it states what
    # offgrid relies on rather than supplying something OpenCode would miss.
    # Written out rather than imported from the module under test: a constant
    # compared against itself moves when the source moves, so it could go red
    # on a missing key and never on a wrong value.
    assert (
        read_written(config_dir)["provider"]["offgrid"]["npm"]
        == "@ai-sdk/openai-compatible"
    )


def test_the_provider_offgrid_writes_is_labelled(configured, config_dir):
    assert read_written(config_dir)["provider"]["offgrid"]["name"]


def test_what_offgrid_writes_says_which_schema_it_is(configured, config_dir):
    # The file is meant to be edited, and this is what an editor completes and
    # validates it against.
    assert read_written(config_dir)["$schema"] == "https://opencode.ai/config.json"


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
    written = json.dumps(read_written(config_dir)).lower()

    assert set(read_written(config_dir)["provider"]) == {"offgrid"}
    assert not [spelling for spelling in RUNTIME_SPELLINGS if spelling in written]


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
