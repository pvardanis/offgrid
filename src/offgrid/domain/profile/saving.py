"""Writing a profile where a later run will find it.

Its own module because writing the file is not reading it: what a save answers
for is the file that was already there, and what a read answers for is what a
person typed into it.
"""

from pathlib import Path

from offgrid.domain.profile.profile import DEFAULT_PATH, Profile
from offgrid.domain.profile.restating import keep_hand_edits
from offgrid.shared.exceptions import ProfileError


def save_profile(profile: Profile, path: Path = DEFAULT_PATH) -> None:
    """Write a profile where a later run will find it.

    A file already saying what offgrid can act on is written over key by key
    rather than replaced, because it is hand-edited: the comments, the blank
    lines and the order somebody chose are theirs, and only the values are
    offgrid's to state. Any other file is written whole.

    The file now holds what nothing can write again, so it is replaced rather
    than written into: a write that stops halfway through a file it truncated
    takes the comments with it, and there is nowhere to read them back from.

    :param profile: The profile to store.
    :param path: Where to write it.

    :raise ProfileError: When the file cannot be written — no folder, no
        permission, no room. Said in offgrid's own words rather than a raw
        `OSError`, so that a save reached from the picker's key fails as a
        sentence a person can act on rather than a traceback on the screen.
    """
    # Dumped as what YAML can carry: a plain dump answers with the enum member
    # itself, which the writer refuses with `cannot represent an object`.
    written = profile.model_dump(mode="json")

    while_writing = path.with_suffix(".yaml.writing")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        while_writing.write_text(keep_hand_edits(_read_what_is_there(path), written))
        while_writing.replace(path)
    except OSError as error:
        raise ProfileError(
            f"Could not write the profile to {path}: {error}. Check the folder "
            "exists and is writable, and that there is room on the disk."
        ) from error


def _read_what_is_there(path: Path) -> str:
    """Read the file a save is about to write over, where it can be read.

    :param path: Where the profile is kept.

    :return: What the file holds, or ``""`` where there is nothing a save
        could carry over — no file, or one this machine will not hand back as
        text. Either way what it held is what the caller is replacing, and a
        file that cannot be read is one nothing can be kept from.
    """
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return ""
