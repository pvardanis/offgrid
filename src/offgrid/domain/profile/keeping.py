"""Reading and writing YAML without losing what a person put in the file.

A profile keeps the comments, the blank lines and the order somebody typed,
so it is read and written through a parser that carries them rather than one
that answers with the values alone.

The library is named here alone, so the rest of the package asks for a mapping
or a piece of text and never for a library.
"""

from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError as YAMLError  # what a caller catches
from ruamel.yaml.constructor import (
    DuplicateKeyError as DuplicateKeyError,  # a caller says it in its own words
)

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
