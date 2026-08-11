import pytest
import yaml

from offgrid.exceptions import ProfileError
from offgrid.profile import Profile, load, save
from offgrid.runtime import RuntimeName


def test_a_saved_profile_reads_back_the_same(tmp_path):
    path = tmp_path / "profile.yaml"
    written = Profile(host="127.0.0.1:1234")
    save(written, path)

    assert load(path) == written


def test_a_profile_is_readable_yaml(tmp_path):
    path = tmp_path / "profile.yaml"
    save(Profile(host="127.0.0.1:1234"), path)

    on_disk = yaml.safe_load(path.read_text())
    assert on_disk["host"] == "127.0.0.1:1234"
    assert on_disk["runtime"] == "lmstudio"


def test_a_profile_typed_by_hand_loads(tmp_path):
    # A regression guard, not a slice. The file is meant to be typed into,
    # and everything but the host has a default, so naming the host is a
    # whole profile — which nothing else here reads without `save` writing it.
    path = tmp_path / "profile.yaml"
    path.write_text("host: 10.0.0.5:4321\n")

    profile = load(path)

    assert profile.host == "10.0.0.5:4321"
    assert profile.runtime is RuntimeName.LMSTUDIO
    assert profile.agent == "claude-code"
    assert profile.model is None


def test_the_runtime_a_profile_names_is_a_name_offgrid_has(tmp_path):
    # A string is validated once and then compared against a literal wherever
    # it is read. The name is what picks the adapter, so it is a type from the
    # moment the file is read.
    path = tmp_path / "profile.yaml"
    path.write_text("host: 10.0.0.5:4321\n")

    assert load(path).runtime is RuntimeName.LMSTUDIO


def test_a_missing_profile_says_how_to_make_one(tmp_path):
    with pytest.raises(ProfileError, match="offgrid setup"):
        load(tmp_path / "absent.yaml")


def test_a_profile_that_is_not_a_mapping_is_refused(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("just a string\n")

    with pytest.raises(ProfileError, match="not a profile"):
        load(path)


def test_a_profile_missing_a_field_names_the_field(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump({"model": "qwen/qwen3.6-35b-a3b"}))

    with pytest.raises(ProfileError, match="host"):
        load(path)


def test_a_profile_can_name_the_model_to_use(tmp_path):
    path = tmp_path / "profile.yaml"
    save(Profile(host="127.0.0.1:1234", model="qwen/qwen3.6-35b-a3b"), path)

    assert load(path).model == "qwen/qwen3.6-35b-a3b"


def test_a_mistyped_key_is_named_rather_than_ignored(tmp_path):
    # A profile is hand-edited, and `modle:` read as "no model named" sends
    # someone looking at the runtime for a mistake that is in the file.
    path = tmp_path / "profile.yaml"
    save(Profile(host="127.0.0.1:1234"), path)
    path.write_text(path.read_text() + "modle: qwen/typo\n")

    with pytest.raises(ProfileError, match="modle"):
        load(path)


def test_a_profile_that_is_not_yaml_is_refused_as_a_profile(tmp_path):
    # An unbalanced bracket is how a hand-edited YAML file usually breaks,
    # and a parser's traceback is not what the person who typed it needs.
    path = tmp_path / "profile.yaml"
    path.write_text("host: [127.0.0.1:1234\nruntime: lmstudio\n")

    with pytest.raises(ProfileError, match=r"profile\.yaml"):
        load(path)


def test_a_runtime_offgrid_cannot_talk_to_is_refused(tmp_path):
    # Naming another runtime changed nothing: offgrid spoke to LM Studio
    # regardless, and `doctor` reported the name back as though it had not.
    path = tmp_path / "profile.yaml"
    save(Profile(host="127.0.0.1:1234"), path)
    path.write_text(path.read_text().replace("lmstudio", "ollama"))

    with pytest.raises(ProfileError, match="runtime"):
        load(path)


def test_an_agent_offgrid_cannot_start_is_refused(tmp_path):
    path = tmp_path / "profile.yaml"
    save(Profile(host="127.0.0.1:1234"), path)
    path.write_text(path.read_text().replace("claude-code", "opencode"))

    with pytest.raises(ProfileError, match="agent"):
        load(path)


def test_a_profile_carrying_a_measured_machine_is_refused(tmp_path):
    # A file `setup` wrote, and one that is still on disks. A limit recorded
    # weeks ago is wrong the moment a runtime moves it at startup, so the file
    # is refused rather than read past.
    path = tmp_path / "profile.yaml"
    path.write_text(
        "host: 127.0.0.1:1234\n"
        "runtime: lmstudio\n"
        "agent: claude-code\n"
        "chip: Apple M1 Max\n"
        "memory_bytes: 68719476736\n"
        "wired_limit_bytes: 60129542144\n"
    )

    with pytest.raises(ProfileError) as refused:
        load(path)

    said = str(refused.value)
    assert "chip" in said
    assert "memory_bytes" in said
    assert "wired_limit_bytes" in said
    assert "offgrid setup" in said
