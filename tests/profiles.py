"""A profile as a person types one, and as the command line builds one.

What a profile's shape refuses, what it says about the model to run, and which
of it a command line beats are separate test modules. Each starts from a
minimal profile — typed out, or written by `setup` — and edits it the way a
person would.
"""

from pathlib import Path

from offgrid.agents import create_agent_config
from offgrid.domain.profile import Profile, dump_yaml, read_yaml
from offgrid.runtimes import create_runtime_config

HOST = "127.0.0.1:1234"

# The whole of a minimal profile: an adapter per port, and where the runtime
# listens. `{host}` is filled in by whoever writes it.
NAMED = "runtime:\n  name: lmstudio\n  host: {host}\nagent:\n  name: claude-code\n"


def build_profile(host: str = HOST, **rest) -> Profile:
    """Build a profile the way the command line builds one.

    :param host: Where the runtime listens.
    :param rest: Whatever else the profile says.

    :return: What a run is made from.
    """
    runtime = create_runtime_config({"name": "lmstudio", "host": host})
    agent = create_agent_config({"name": "claude-code"}, runtime_host=host)

    return Profile(runtime=runtime, agent=agent, **rest)


def add_to_section(home: Path, section: str, **said) -> None:
    """Type keys into one section of the stored profile, as a person would.

    :param home: Where offgrid keeps the profile.
    :param section: Which section to type into, as the file spells it.
    :param said: What to say in it.
    """
    written = _read(home)
    written[section] = (written[section] or {}) | said

    _write(home, written)


def drop_section(home: Path, section: str) -> None:
    """Take a whole section out of the stored profile, as a hand-edit may.

    :param home: Where offgrid keeps the profile.
    :param section: Which section to take out, as the file spells it.
    """
    written = _read(home)
    del written[section]

    _write(home, written)


def read_written(text: str) -> dict:
    """Read a profile file as the mapping a test asks questions of.

    :param text: What the file holds.

    :return: The mapping in it.
    """
    body = read_yaml(text)
    assert isinstance(body, dict)

    return body


def _read(home: Path) -> dict:
    """Read what the stored profile holds.

    :param home: Where offgrid keeps the profile.

    :return: The mapping in the file.
    """
    return read_written((home / "profile.yaml").read_text())


def _write(home: Path, written: dict) -> None:
    """Write a mapping back where the stored profile is.

    :param home: Where offgrid keeps the profile.
    :param written: What the file should hold.
    """
    (home / "profile.yaml").write_text(dump_yaml(written))
