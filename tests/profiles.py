"""A profile as a person types one, and as the command line builds one.

What a profile's shape refuses, what it says about the model to run, and which
of it a command line beats are three test modules, and all of them start from
the same minimal file and then edit it the way a person would.
"""

from pathlib import Path

import yaml

from offgrid.agents import create_agent_config
from offgrid.domain.profile import Profile
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


def _read(home: Path) -> dict:
    """Read what the stored profile holds.

    :param home: Where offgrid keeps the profile.

    :return: The mapping in the file.
    """
    return yaml.safe_load((home / "profile.yaml").read_text())


def _write(home: Path, written: dict) -> None:
    """Write a mapping back where the stored profile is.

    :param home: Where offgrid keeps the profile.
    :param written: What the file should hold.
    """
    (home / "profile.yaml").write_text(yaml.safe_dump(written, sort_keys=False))
