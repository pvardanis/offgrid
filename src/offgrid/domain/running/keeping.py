"""What a run keeps of a configuration somebody may have edited.

`configure` has one file to decide about at a time, and existence is not the
question — a file that is there but says nothing is exactly as unusable to the
agent as no file, and leaving it alone leaves the agent nothing to load and
says nothing about why. What is being asked is whether there is an edit to
lose, which is what these answer.

Three things follow from answering it that way, and none of them is hidden. A
file that parses is an edit and is kept whole, so one edited down to a key
offgrid never wrote stays that way; a key offgrid adds in a later version
reaches no file that is already there; and both are silent. Writing either back
would answer a deliberate edit with a run that quietly disagrees with the file,
because the key likeliest to be missing is the one deciding something offgrid
promised — sharing off, a hosted tool denied. What a person can act on instead
is a guard that reads the file and refuses the run, which is what
`hosted_tools.py` is for.

Whether the file holds an edit is asked of its text rather than of what the
text parses to, because `null` is a document a person could have left and is
also how "nothing" is spelled: deciding off the parsed value would write over
that one file and no other.
"""

import json
from pathlib import Path

from offgrid.shared.exceptions import AgentSettingsError

INDENT = 2
"""How far the settings offgrid writes are indented, so they read as a file."""


def read_what_is_kept(written: Path) -> str | None:
    """Read what a file holds that a run must not write over.

    An empty file holds no edit, so it answers the same as no file at all:
    whatever put it there — a write that stopped, an editor saving over it, a
    person cutting it down — left nothing anybody chose.

    A symbolic link to a file that is there is followed, wherever it points,
    because pointing a configuration somewhere else is a thing people do on
    purpose. One whose target is gone is refused instead: it reads as absent
    by everything that follows it, so a write would create the target rather
    than the file — somewhere offgrid never looked, and with nothing said.

    What is refused is therefore the link that would create something, not
    the link that leaves the directory. A live link out of it is followed,
    and an empty file at the far end is written into like any other.

    :param written: The file to decide about.

    :return: What it holds, or nothing where there is no edit to keep.

    :raise AgentSettingsError: When it is a link whose target is not there, or
        cannot be read as text.
    """
    if written.is_symlink() and not written.exists():
        raise AgentSettingsError(
            f"{written} is a link to {written.readlink()}, which nothing can "
            "read: it is either not there or leads back to itself. Writing "
            "would create a file at the far end rather than configure this "
            "one. Point the link at the settings you meant, or delete it and "
            "offgrid writes a file here."
        )

    try:
        body = written.read_text()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        raise AgentSettingsError(
            f"{written} cannot be read: {error}. Fix what it is or what owns it, "
            "or delete it and offgrid writes one."
        ) from error

    return body if body.strip() else None


def write_where_nothing_is_kept(written: Path, content: str) -> None:
    """Write a file, unless it holds an edit somebody made.

    :param written: The file to decide about.
    :param content: What to write where there is no edit to keep.

    :raise AgentSettingsError: When what is there cannot be read.
    :raise OSError: When it cannot be written.
    """
    if read_what_is_kept(written) is None:
        written.write_text(content)


def write_settings_where_nothing_is_kept(written: Path, settings: dict) -> None:
    """Write a settings file, unless it holds an edit somebody made.

    What is there is parsed as well as read, so that a file no agent could
    load is refused rather than left for the agent to fail on. It is the text
    that decides whether to write, not what the text parsed to.

    :param written: The settings file to decide about.
    :param settings: What to write where there is no edit to keep.

    :raise AgentSettingsError: When what is there cannot be read, or is not
        JSON.
    :raise OSError: When it cannot be written.
    """
    body = read_what_is_kept(written)

    if body is None:
        written.write_text(json.dumps(settings, indent=INDENT) + "\n")

        return

    # Read for the refusal rather than for the value: what an edit parses to
    # is the agent's business, and only that it parses at all is this one's.
    read_as_json(body, written)


def read_as_json(body: str, written: Path) -> object:
    """Read what a settings file holds as the JSON it claims to be.

    Parsing is apart from reading because bytes that are not text never reach
    the parser, and calling that bad JSON sends somebody looking for a bracket.
    `UnicodeDecodeError` is a `ValueError`, so it would.

    It takes the text rather than the path so that a caller which has already
    asked whether there is an edit does not ask the file twice — and so that
    what it parses to never has to stand in for whether there was anything to
    parse. `null` is a document somebody could have left, and a caller reading
    absence off the parsed value would call that file empty.

    :param body: What the file holds.
    :param written: The file it came from, to say which one is wrong.

    :return: What it holds, in whatever shape it was written.

    :raise AgentSettingsError: When it is not JSON.
    """
    try:
        return json.loads(body)
    except ValueError as error:
        raise AgentSettingsError(
            f"{written} is not readable as JSON: {error}. Fix it, or delete it "
            "and offgrid writes one."
        ) from error
