"""Windows a runtime was asked for and did not grant, kept between runs.

A runtime that discards the window a run asks for answers the next run the
same way, so asking again costs a release and a load that change nothing —
and where the runtime caches a prompt prefix, the load throws the cache away.
The fact is kept rather than the verdict: what was asked, what came back, and
when. Keyed on the runtime, the model and the window together: two models on
one server disagree about this, and one model may be reached at two addresses.

Read as a file a person may have opened: a record it refuses is one it says
so about, the same way a profile is read. Nothing expires — deleting the file
is how a person says to ask again.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic import BeforeValidator as Before

from offgrid.domain.running.model import refuse_a_yes_or_no
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError
from offgrid.shared.home import OFFGRID_HOME

# Beside the profile, which is where offgrid keeps what outlives a run.
DEFAULT_PATH = OFFGRID_HOME / "discarded-windows.json"

Window = Annotated[int, Before(refuse_a_yes_or_no), Field(gt=0)]


class DiscardedWindow(BaseModel):
    """A window a run asked for, beside the one the runtime served instead.

    Keys it does not name are refused, so a hand-edited record with a typo in
    it is reported rather than read as a record about nothing.

    :param host: Address the runtime listens on.
    :param identifier: The model that was asked for.
    :param asked_for: The window the run asked to hold it at.
    :param served: The window the runtime is serving it at instead.
    :param noticed_at: When offgrid saw it, as ``2026-08-21T14:31:07``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    identifier: str
    asked_for: Window
    served: Window
    noticed_at: str

    @property
    def dated(self) -> str:
        """The day it was noticed, which is as fine as anyone reads one.

        :return: The date, as ``2026-08-21``.
        """
        return self.noticed_at.split("T")[0]


DISCARDED_WINDOWS = TypeAdapter(list[DiscardedWindow])


def save_discarded_window(
    *, host: str, identifier: str, asked_for: int, served: int, file_path: Path
) -> None:
    """Keep that a runtime did not grant a window, beside the ones before it.

    Every window a runtime discarded is kept, not only the last, so a run
    going back to an earlier one is not put a question already answered.

    Stamped here rather than by the caller, so that a record without a day on
    it never exists. Written beside the file and moved onto it, so that a run
    interrupted mid-write leaves the last answer rather than half of this one.

    :param host: Address the runtime listens on.
    :param identifier: The model that was asked for.
    :param asked_for: The window the run asked to hold it at.
    :param served: The window the runtime is serving it at instead.
    :param file_path: Where to keep it.

    :raise OSError: When there is nowhere to write.
    :raise DiscardedWindowsUnreadableError: When what is there will not read,
        since replacing one record means writing the rest back.
    """
    noticed = DiscardedWindow(
        host=host,
        identifier=identifier,
        asked_for=asked_for,
        served=served,
        noticed_at=datetime.now().isoformat(timespec="seconds"),
    )

    asked = (host, identifier, asked_for)
    others = [
        record
        for record in _read_all(file_path)
        if (record.host, record.identifier, record.asked_for) != asked
    ]

    file_path.parent.mkdir(parents=True, exist_ok=True)
    beside = file_path.with_name(f"{file_path.name}.writing")
    beside.write_text(json.dumps([r.model_dump() for r in [*others, noticed]]))
    os.replace(beside, file_path)


def read_discarded_windows(host: str, file_path: Path) -> tuple[DiscardedWindow, ...]:
    """Read back what one runtime did with the windows it was asked for.

    Every record for the runtime at once: a command that reads them one at a
    time opens the file once per question, and the answers come from the same
    moment either way. How to look one up is the caller's to say.

    :param host: Address the runtime listens on.
    :param file_path: Where they would have been kept.

    :return: What was kept about this runtime, in the order it was written.

    :raise DiscardedWindowsUnreadableError: When the file is there and will
        not read.
    """
    return tuple(record for record in _read_all(file_path) if record.host == host)


def _read_all(file_path: Path) -> list[DiscardedWindow]:
    """Read every record the file holds.

    A file that is not there is every machine before the first window is
    discarded, so it is no memory rather than a fault. Anything else is a
    fault: a run that cannot read this asks for a window it has already been
    refused, and pays the reload for it.

    :param file_path: Where they would have been kept.

    :return: What was kept, which is nothing where there is no file.

    :raise DiscardedWindowsUnreadableError: When it is there and will not read.
    """
    try:
        return DISCARDED_WINDOWS.validate_json(file_path.read_bytes())
    except FileNotFoundError:
        return []
    except (OSError, ValidationError) as error:
        raise DiscardedWindowsUnreadableError(
            f"{file_path} could not be read: {error}. Fix what is there or "
            "what owns it, or delete it and offgrid starts a new one."
        ) from error
