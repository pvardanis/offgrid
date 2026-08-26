"""Reading and writing YAML without losing what a person put in the file.

The profile is advertised as hand-editable, so what offgrid writes back has to
be the file that was there with the values it now says — not the same mapping
printed again. Comments, blank lines and the order somebody chose are part of
the file, and a save that dropped them would make the invitation to edit
conditional on never saving.

The parser is named here alone, so the rest of the package asks for a mapping
or a piece of text and never for a library.
"""

from io import StringIO

from ruamel.yaml import YAML, YAMLError

# Wide enough that no value offgrid writes is folded onto a second line: a
# wrapped model name is still the name, but nobody hand-edits it that way.
LINE_WIDTH = 4096

_yaml = YAML()
_yaml.width = LINE_WIDTH
_yaml.preserve_quotes = True


def read_yaml(text: str) -> object:
    """Read a piece of YAML, keeping what a person typed around the values.

    :param text: What the file holds.

    :return: What it says, as the mapping, list or scalar it is.

    :raise YAMLError: When it is not YAML.
    """
    return _yaml.load(text)


def dump_yaml(said: object) -> str:
    """Write out YAML, in the order it is stated in.

    :param said: What to write.

    :return: The text of it.
    """
    written = StringIO()
    _yaml.dump(said, written)

    return written.getvalue()


def keep_hand_edits(already: str, said: dict) -> str:
    """State what a mapping says over the file that is already there.

    A key the file names is answered where it stands; a key it never named is
    written after what is there, which is where the next one would be typed. A
    key the file holds and the mapping does not is taken out, so the file goes
    on saying what offgrid can act on and nothing else.

    :param already: What the file holds, or ``""`` where there is no file.
    :param said: What it should now say.

    :return: The text to write, carrying whatever was there around the values.

    :raise YAMLError: Never — a file that is not YAML is written over rather
        than merged into, since there is nothing in it to keep.
    """
    document = _read_mapping(already)

    if document is None:
        return dump_yaml(said)

    _restate(document, said)

    return dump_yaml(document)


def _read_mapping(text: str) -> dict | None:
    """Read a piece of text as the mapping to write over.

    :param text: What the file holds.

    :return: The mapping, or ``None`` where there is nothing to keep — the
        file is absent, unparseable, or holds something that is not a mapping.
    """
    try:
        body = read_yaml(text)
    except YAMLError:
        return None

    return body if isinstance(body, dict) else None


def _restate(document: dict, said: dict) -> None:
    """Say what a mapping says in a document, key by key and in place.

    :param document: The mapping as the file holds it.
    :param said: What it should now say.
    """
    for dropped in [key for key in document if key not in said]:
        del document[dropped]

    for key, value in said.items():
        held = document.get(key)

        if isinstance(value, dict) and isinstance(held, dict):
            _restate(held, value)
        else:
            document[key] = value
