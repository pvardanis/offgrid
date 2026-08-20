"""What a hand-edited profile does, and which ones are refused.

Read through `binding.py`, because a section only becomes the config an adapter
is built from once something knows which adapters there are. What the `model`
section says is in `test_profile_model.py`.
"""

import pytest
import yaml

from offgrid.binding import read_profile
from offgrid.domain.profile import Profile, save_profile
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.runtime import RuntimeName
from offgrid.runtimes import create_runtime_config
from offgrid.shared.exceptions import ProfileError
from tests.doubles import StandInAgentConfig
from tests.profiles_on_disk import HOST, NAMED, build_profile


def test_a_saved_profile_reads_back_the_same(tmp_path):
    path = tmp_path / "profile.yaml"
    written = build_profile()
    save_profile(written, path)

    assert read_profile(path) == written


def test_a_profile_is_readable_yaml(tmp_path):
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(), path)

    on_disk = yaml.safe_load(path.read_text())
    assert on_disk["runtime"] == {"host": HOST, "name": "lmstudio"}
    assert on_disk["agent"] == {"name": "claude-code"}


def test_a_profile_writes_nothing_offgrid_settled_for_itself(tmp_path):
    # The agent is told where the runtime listens, and it is the runtime
    # section that says so. Written under `agent:` too, it would be a second
    # answer that a hand-edit could put out of step with the first.
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(), path)

    assert "runtime_host" not in path.read_text()


def test_a_setting_only_one_adapter_reads_is_written_down(tmp_path):
    # A section is where an adapter's own settings go, which is the whole of
    # what this shape is for. The field is annotated on the base, and pydantic
    # serializes through the annotation rather than the object — so a setting
    # the base does not declare goes out of the file without a word, and the
    # next `setup` writes the profile back without it.
    path = tmp_path / "profile.yaml"
    runtime = create_runtime_config({"name": "lmstudio", "host": HOST})
    agent = StandInAgentConfig(runtime_host=HOST, theme="light")

    save_profile(Profile(runtime=runtime, agent=agent), path)

    assert yaml.safe_load(path.read_text())["agent"]["theme"] == "light"


def test_a_profile_typed_by_hand_loads(tmp_path):
    # The file is meant to be typed into, and this is the whole of one: an
    # adapter per port and where the runtime listens.
    path = tmp_path / "profile.yaml"
    path.write_text(NAMED.format(host="10.0.0.5:4321"))

    profile = read_profile(path)

    assert profile.runtime.host == "10.0.0.5:4321"
    assert profile.runtime.name is RuntimeName.LMSTUDIO
    assert profile.agent.name is AgentName.CLAUDE_CODE
    assert profile.model is None


def test_the_agent_is_told_where_the_runtime_listens(tmp_path):
    # An agent that writes where to talk into a config file of its own needs
    # it before `configure` runs, and its own section never says it.
    path = tmp_path / "profile.yaml"
    path.write_text(NAMED.format(host="10.0.0.5:4321"))

    assert read_profile(path).agent.runtime_host == "10.0.0.5:4321"


def test_the_runtime_a_profile_names_is_a_name_offgrid_has(tmp_path):
    # A string is validated once and then compared against a literal wherever
    # it is read. The name is what picks the adapter, so it is a type from the
    # moment the file is read.
    path = tmp_path / "profile.yaml"
    path.write_text(NAMED.format(host="10.0.0.5:4321"))

    assert read_profile(path).runtime.name is RuntimeName.LMSTUDIO


def test_the_agent_a_profile_names_is_a_name_offgrid_has(tmp_path):
    # The name is what picks the adapter offgrid launches, so it is a type
    # from the moment the file is read rather than a string checked once.
    path = tmp_path / "profile.yaml"
    path.write_text(NAMED.format(host="10.0.0.5:4321"))

    assert read_profile(path).agent.name is AgentName.CLAUDE_CODE


def test_a_missing_profile_says_how_to_make_one(tmp_path):
    with pytest.raises(ProfileError, match="offgrid setup"):
        read_profile(tmp_path / "absent.yaml")


def test_a_profile_that_is_not_a_mapping_is_refused(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("just a string\n")

    with pytest.raises(ProfileError, match="not a profile"):
        read_profile(path)


def test_a_profile_missing_a_field_names_the_field(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump({"runtime": {"name": "lmstudio"}}))

    with pytest.raises(ProfileError, match="host"):
        read_profile(path)


@pytest.mark.parametrize(
    ("written", "port", "offered"),
    [
        (
            "runtime:\n  host: 10.0.0.5:4321\nagent:\n  name: claude-code\n",
            "runtime",
            "lmstudio",
        ),
        ("runtime:\n  name: lmstudio\n  host: 10.0.0.5:4321\n", "agent", "claude-code"),
    ],
    ids=["the runtime", "the agent"],
)
def test_a_section_naming_no_adapter_is_refused(tmp_path, written, port, offered):
    # Which adapter to use is the whole point of a section, and guessing one
    # is how a profile silently runs something nobody asked for. It is not
    # defaulted: `setup` writes the name, and a hand-edit has to say it.
    path = tmp_path / "profile.yaml"
    path.write_text(written)

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert f"`{port}` section" in said
    assert "names no adapter" in said
    assert offered in said


def test_a_mistyped_key_is_named_rather_than_ignored(tmp_path):
    # A profile is hand-edited, and `modle:` read as "no model named" sends
    # someone looking at the runtime for a mistake that is in the file.
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(), path)
    path.write_text(path.read_text() + "modle: qwen/typo\n")

    with pytest.raises(ProfileError, match="modle"):
        read_profile(path)


def test_a_profile_that_is_not_yaml_is_refused_as_a_profile(tmp_path):
    # An unbalanced bracket is how a hand-edited YAML file usually breaks,
    # and a parser's traceback is not what the person who typed it needs.
    path = tmp_path / "profile.yaml"
    path.write_text("runtime:\n  name: [lmstudio\n")

    with pytest.raises(ProfileError, match=r"profile\.yaml"):
        read_profile(path)


def test_a_runtime_offgrid_cannot_talk_to_is_refused(tmp_path):
    # Naming another runtime changed nothing: offgrid spoke to LM Studio
    # regardless, and `doctor` reported the name back as though it had not.
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(), path)
    path.write_text(path.read_text().replace("lmstudio", "ollama"))

    with pytest.raises(ProfileError, match="ollama"):
        read_profile(path)


def test_an_agent_offgrid_cannot_start_is_refused(tmp_path):
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(), path)
    path.write_text(path.read_text().replace("claude-code", "opencode"))

    with pytest.raises(ProfileError, match="opencode"):
        read_profile(path)


def test_a_key_the_agent_it_names_does_not_read_is_refused(tmp_path):
    # The section belongs to whichever adapter its name picks, so this is the
    # only place a typo under `agent:` can be caught — and it is caught, not
    # dropped. The message names the section, the adapter, and the key.
    path = tmp_path / "profile.yaml"
    path.write_text(
        f"runtime:\n  name: lmstudio\n  host: {HOST}\n"
        "agent:\n  name: claude-code\n  theme: dark\n"
    )

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "`agent` section" in said
    assert "claude-code" in said
    assert "theme" in said


def test_the_window_an_agent_needs_to_start_is_not_a_profile_key(tmp_path):
    # The floor is what the agent needs, not what anyone prefers, so a file
    # naming it could only assert something false about the agent — bought
    # with a failed launch after a load that has already been paid for.
    #
    # A guard rather than a slice: a key no adapter reads was refused before
    # the floor existed, and this pins the floor among them.
    path = tmp_path / "profile.yaml"
    path.write_text(
        f"runtime:\n  name: lmstudio\n  host: {HOST}\n"
        "agent:\n  name: claude-code\n  context_floor: 8000\n"
    )

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "`agent` section" in said
    assert "context_floor" in said


def test_a_key_offgrid_settles_itself_is_refused_rather_than_taken(tmp_path):
    # `runtime_host` is a field of the agent's config, filled from the runtime
    # section. A file naming it would otherwise be overridden in silence — the
    # one dropped key `extra="forbid"` cannot catch.
    path = tmp_path / "profile.yaml"
    path.write_text(
        f"runtime:\n  name: lmstudio\n  host: {HOST}\n"
        "agent:\n  name: claude-code\n  runtime_host: 10.0.0.5:4321\n"
    )

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "`agent` section" in said
    assert "runtime_host" in said
    assert "offgrid settles itself" in said


def test_a_profile_written_flat_is_refused_with_the_shape_it_now_wants(tmp_path):
    # The shape a working profile is in before it is nested. Naming the first
    # key that does not fit leaves the reader guessing at the rest of it.
    path = tmp_path / "profile.yaml"
    path.write_text("host: 127.0.0.1:1234\nruntime: lmstudio\nagent: claude-code\n")

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "runtime:\n  name: lmstudio\n  host: 127.0.0.1:1234" in said
    assert "agent:\n  name: claude-code" in said


def test_a_profile_naming_a_port_without_a_section_is_refused_the_same_way(tmp_path):
    # Half-nested, which is how a hand-edit of the flat shape usually lands:
    # `host` moved under the runtime, and the names left where they were.
    path = tmp_path / "profile.yaml"
    path.write_text("runtime: lmstudio\nagent: claude-code\n")

    with pytest.raises(ProfileError, match="a section per adapter"):
        read_profile(path)


def test_a_profile_carrying_a_measured_machine_is_refused(tmp_path):
    # A file `setup` wrote, and one that is still on disks. A limit recorded
    # weeks ago is wrong the moment a runtime moves it at startup, so the file
    # is refused rather than read past.
    path = tmp_path / "profile.yaml"
    path.write_text(
        NAMED.format(host=HOST) + "chip: Apple M1 Max\n"
        "memory_bytes: 68719476736\n"
        "wired_limit_bytes: 60129542144\n"
    )

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "chip" in said
    assert "memory_bytes" in said
    assert "wired_limit_bytes" in said
    assert "offgrid setup" in said
