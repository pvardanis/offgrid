"""Stating what a profile says over the file that is already there.

The file is advertised as hand-editable, so what offgrid writes back has to be
the file that was there with the values it now says — not the same mapping
printed again. Comments, blank lines and the order somebody chose are part of
the file, and a save that dropped them would make the invitation to edit
conditional on never saving.

What cannot be said that way is said whole. A file is either the one that was
read, restated, or a fresh one; nothing in between goes to disk.
"""

from offgrid.domain.profile.keeping import YAMLError, dump_yaml, read_yaml


def keep_hand_edits(existing_text: str, new_content: dict) -> str:
    """State what a mapping says over the file that is already there.

    A key the file names is answered where it stands, and a key it never named
    is written after what is there, which is where the next one would be typed.

    A file holding a key the mapping does not is written whole instead, and so
    is one that is not YAML at all. There is nothing to keep in either: a
    comment stands above the key it is about, and taking that key out would
    leave the comment saying something false about whatever follows it.

    What comes back is checked against what was read, line for line, and the
    file is written whole where the two disagree anywhere but the end. A key
    written into a section that something follows lands after the blank line
    and the comment that introduce whatever is next — which is the same
    comment, over something else it does not describe.

    :param existing_text: What the file holds, or ``""`` where there is no
        file.
    :param new_content: What it should now say.

    :return: The text to write, carrying whatever was there around the values.
    """
    existing_content = _read_mapping(existing_text)

    if existing_content is None or not _holds_only(existing_content, new_content):
        return dump_yaml(new_content)

    _restate(existing_content, new_content)
    new_text = dump_yaml(existing_content)

    if not _stands_where_it_stood(existing_text, new_text):
        return dump_yaml(new_content)

    return new_text


def _read_mapping(existing_text: str) -> dict | None:
    """Read a piece of text as the mapping to write over.

    :param existing_text: What the file holds.

    :return: The mapping, or ``None`` where there is nothing to keep — the
        file is absent, unparseable, or holds something that is not a mapping.
    """
    try:
        body = read_yaml(existing_text)
    except YAMLError:
        return None

    return body if isinstance(body, dict) else None


def _holds_only(existing_content: dict, new_content: dict) -> bool:
    """Say whether what the file holds names nothing the mapping does not.

    :param existing_content: The mapping as the file holds it.
    :param new_content: What it should now say.

    :return: ``True`` where every key the file names is one the mapping has,
        section by section. A key the file leaves out is not a disagreement:
        it is written in. A key holding a section where the mapping holds a
        value, or the reverse, is one — restating it would take out whatever
        the section held, comments and all.
    """
    return all(
        key in new_content and _agrees(held, new_content[key])
        for key, held in existing_content.items()
    )


def _agrees(held: object, value: object) -> bool:
    """Say whether what the file holds under a key is the shape stated for it.

    :param held: What the file holds there.
    :param value: What the mapping says there.

    :return: ``True`` where neither is a section, or where both are and the
        section agrees the same way.
    """
    if isinstance(held, dict) or isinstance(value, dict):
        return (
            isinstance(held, dict)
            and isinstance(value, dict)
            and _holds_only(held, value)
        )

    return True


def _stands_where_it_stood(existing_text: str, new_text: str) -> bool:
    """Say whether a file came back as itself, with anything new at the end.

    Line for line, because that is what a person sees: a comment two lines
    below where it was is a comment about something else. A line offgrid
    restated is the same line — the key at the same indent, whatever the value
    now says — and a line after the end of what was there is a key the file
    never named.

    :param existing_text: What the file held.
    :param new_text: What it would now hold.

    :return: ``True`` where nothing moved.
    """
    stood = existing_text.splitlines()
    stands = new_text.splitlines()

    if len(stands) < len(stood):
        return False

    return all(
        _says_the_same_key(was, now)
        for was, now in zip(stood, stands[: len(stood)], strict=True)
    )


def _says_the_same_key(was: str, now: str) -> bool:
    """Say whether two lines are the same line, whatever value each carries.

    :param was: The line as the file had it.
    :param now: The line as it would be written.

    :return: ``True`` where both name the same key at the same indent, or are
        the same text outright.
    """
    if was == now:
        return True

    return ":" in was and ":" in now and was.split(":")[0] == now.split(":")[0]


def _restate(existing_content: dict, new_content: dict) -> None:
    """Say what a mapping says in what the file holds, key by key and in place.

    :param existing_content: The mapping as the file holds it.
    :param new_content: What it should now say.
    """
    for key, value in new_content.items():
        held = existing_content.get(key)

        if isinstance(value, dict) and isinstance(held, dict):
            _restate(held, value)
        else:
            existing_content[key] = value
