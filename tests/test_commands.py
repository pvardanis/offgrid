"""Every command there is, answered for by the suite before it runs.

`tests/commands.py` says which commands read the machine and which name the
profile, and a list is worth only what checks it. A command missing from one
is a command nothing stands in for: its own tests then measure the developer's
Mac and write their real home, and they pass while doing it, because a patch
that was never applied fails nothing.

This is the check, and it reads the commands from the command line rather than
from a list of its own — a list guarded by a second list is the same hole one
file further down.
"""

import importlib
from types import ModuleType

from offgrid.cli import app
from tests.commands import MEASURING, READING_THE_PROFILE

# What a command module holds when it reads one of these for itself, which is
# what decides whether a test has to stand it in.
MEASURES = "detect"
NAMES_THE_PROFILE = "DEFAULT_PATH"


def _commands() -> set[str]:
    """Every command the command line answers to.

    :return: The name of each, as the module it is written in is named.
    """
    named = {
        str(getattr(command.callback, "__name__", ""))
        for command in app.registered_commands
    }

    if not named:
        raise AssertionError(
            "the command line answers to no commands at all, so this checks "
            "nothing. Attach them in offgrid/cli/__init__.py."
        )

    return named


def _written_in(command: str) -> ModuleType:
    """The module a command is written in.

    :param command: Which command.

    :return: Its module, for reading what names it holds.
    """
    return importlib.import_module(f"offgrid.cli.{command}")


def _holding(name: str) -> set[str]:
    """Every command whose module holds a name of its own.

    :param name: The name to look for, as the module binds it.

    :return: The commands that would need standing in for.
    """
    return {command for command in _commands() if hasattr(_written_in(command), name)}


def test_every_command_that_measures_the_machine_is_stood_in_for():
    assert _holding(MEASURES) == set(MEASURING), (
        "MEASURING in tests/commands.py does not name every command that "
        f"reads `{MEASURES}`. A command left out of it measures the machine "
        "the suite is running on."
    )


def test_every_command_that_names_the_profile_is_stood_in_for():
    assert _holding(NAMES_THE_PROFILE) == set(READING_THE_PROFILE), (
        "READING_THE_PROFILE in tests/commands.py does not name every command "
        f"that reads `{NAMES_THE_PROFILE}`. A command left out of it reads and "
        "writes the real profile, in the developer's own home."
    )
