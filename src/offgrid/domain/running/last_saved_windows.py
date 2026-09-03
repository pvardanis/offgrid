"""The window each model was last saved at, kept between runs.

The runtime cannot supply this: a cold model is served at no window, so its
`Model.context_window` is ``None`` until something holds it. offgrid keeps what
a model was last saved at instead, so the picker can default each model to the
window it last ran at rather than a fixed one.

Keyed on the model alone: it is one number per model, not per runtime or
address, since it is what a person chose to run that model at rather than what
any server did with it. A fresh save replaces the model's record — the store is
what it was last saved at, not every window it was ever saved at.

Read as a file a person may have opened: a record it refuses is one it says so
about, the same way a profile and the discarded-windows file are. A file that
is not there is no memory rather than a fault, since that is every model before
one is first saved.
"""

import os
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic import BeforeValidator as Before

from offgrid.domain.running.model import refuse_a_yes_or_no
from offgrid.shared.exceptions import LastSavedWindowsUnreadableError
from offgrid.shared.home import OFFGRID_HOME

# Beside the profile and the discarded-windows file, where offgrid keeps what
# outlives a run.
DEFAULT_PATH = OFFGRID_HOME / "last-saved-windows.json"

Window = Annotated[int, Before(refuse_a_yes_or_no), Field(gt=0)]


class LastSavedWindow(BaseModel):
    """The window a model was saved at, so a later run can open on it.

    Keys it does not name are refused, so a hand-edited record with a typo in
    it is reported rather than read as a record about nothing.

    :param identifier: The model that was saved.
    :param window: The window it was saved at.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str
    window: Window


LAST_SAVED_WINDOWS = TypeAdapter(list[LastSavedWindow])


def save_last_saved_window(*, identifier: str, window: int, file_path: Path) -> None:
    """Keep the window a model was saved at, replacing the one kept before it.

    One record per model, because the store is what it was last saved at rather
    than every window it was ever saved at: a fresh save moves the model's
    record and leaves every other model's alone.

    Written beside the file and moved onto it, so that a run interrupted
    mid-write leaves the last record rather than half of this one.

    :param identifier: The model that was saved.
    :param window: The window it was saved at.
    :param file_path: Where to keep it.

    :raise OSError: When there is nowhere to write.
    :raise LastSavedWindowsUnreadableError: When what is there will not read,
        since replacing one record means writing the rest back.
    """
    saved = LastSavedWindow(identifier=identifier, window=window)

    others = [
        record for record in _read_all(file_path) if record.identifier != identifier
    ]

    file_path.parent.mkdir(parents=True, exist_ok=True)
    beside = file_path.with_name(f"{file_path.name}.writing")
    beside.write_bytes(LAST_SAVED_WINDOWS.dump_json([*others, saved]))
    os.replace(beside, file_path)


def read_last_saved_windows(file_path: Path) -> dict[str, int]:
    """Read back the window each model was last saved at.

    Every model at once, as a mapping the caller looks a model up in: a model
    with no record is absent from it, which is how the picker tells one it has
    a window kept for from one it must fall back to a ceiling for.

    :param file_path: Where they would have been kept.

    :return: The window each model was last saved at, keyed on the model, which
        is empty where there is no file. A model saved more than once in a
        hand-edited file reads as the last window written for it.

    :raise LastSavedWindowsUnreadableError: When the file is there and will not
        read.
    """
    return {record.identifier: record.window for record in _read_all(file_path)}


def _read_all(file_path: Path) -> list[LastSavedWindow]:
    """Read every record the file holds.

    A file that is not there is every model before one is first saved, so it is
    no memory rather than a fault. Anything else is a fault: a picker that
    cannot read this defaults a model to a window nobody chose.

    :param file_path: Where they would have been kept.

    :return: What was kept, which is nothing where there is no file.

    :raise LastSavedWindowsUnreadableError: When it is there and will not read.
    """
    try:
        return LAST_SAVED_WINDOWS.validate_json(file_path.read_bytes())
    except FileNotFoundError:
        return []
    except (OSError, ValidationError) as error:
        raise LastSavedWindowsUnreadableError(
            f"{file_path} could not be read: {error}. Fix what is there or "
            "what owns it, or delete it and offgrid starts a new one."
        ) from error
