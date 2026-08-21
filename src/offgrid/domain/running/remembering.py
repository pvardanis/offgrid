"""Windows a runtime was asked for and did not grant, kept between runs.

A runtime that discards the window a run asks for answers the next run the
same way, so asking again costs a release and a load that change nothing —
and where the runtime caches a prompt prefix, the load throws the cache away.
The fact is kept rather than the verdict: what was asked, what came back, and
when. Keyed on the runtime and the model together, because it is a property
of one model on one server rather than of either alone. Nothing expires:
deleting the file is how a person says to ask again.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeGuard

from offgrid.shared.home import OFFGRID_HOME

# Beside the profile, because it is offgrid's own record of a run rather than
# anything a person configured.
DEFAULT_PATH = OFFGRID_HOME / "discarded-windows.json"


@dataclass(frozen=True)
class DiscardedWindow:
    """A window a run asked for, beside the one the runtime served instead.

    :param host: Address the runtime listens on.
    :param identifier: The model that was asked for.
    :param asked_for: The window the run asked to hold it at.
    :param served: The window the runtime is serving it at instead.
    :param noticed_at: When offgrid saw it, as ``2026-08-21T14:31:07``. Left
        out, it is stamped as the record is kept.
    """

    host: str
    identifier: str
    asked_for: int
    served: int
    noticed_at: str = ""


def remember_discarded_window(
    discarded: DiscardedWindow, file_path: Path = DEFAULT_PATH
) -> None:
    """Keep that a runtime did not grant a window, replacing its last answer.

    A runtime that has started granting windows is described by what it just
    did, not by what it did once.

    :param discarded: What was asked for, and what came back.
    :param file_path: Where to keep it.

    :raise OSError: When there is nowhere to write. Whether that is worth
        stopping for is the caller's: a model already held is worth running
        against even where nothing can be kept.
    """
    seen = discarded.noticed_at or datetime.now().isoformat(timespec="seconds")
    stamped = DiscardedWindow(
        discarded.host,
        discarded.identifier,
        discarded.asked_for,
        discarded.served,
        seen,
    )

    kept = [
        record
        for record in _read_all(file_path)
        if (record.host, record.identifier) != (stamped.host, stamped.identifier)
    ]

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps([asdict(record) for record in [*kept, stamped]]))


def read_discarded_window(
    host: str, identifier: str, file_path: Path = DEFAULT_PATH
) -> DiscardedWindow | None:
    """Read back what a runtime did with a window it was asked for.

    :param host: Address the runtime listens on.
    :param identifier: The model to read about.
    :param file_path: Where it would have been kept.

    :return: What was kept, or ``None`` where nothing was. A file offgrid
        cannot read back is one it overwrites, so it is worth no message.
    """
    for record in _read_all(file_path):
        if (record.host, record.identifier) == (host, identifier):
            return record

    return None


def _read_all(file_path: Path) -> list[DiscardedWindow]:
    """Read every record the file holds, skipping any that is not one.

    :param file_path: Where they would have been kept.

    :return: What was kept, which is nothing where the file is not offgrid's.
    """
    try:
        kept = json.loads(file_path.read_text())
    except (OSError, ValueError):
        return []

    if not isinstance(kept, list):
        return []

    return [record for record in map(_as_record, kept) if record is not None]


def _as_record(entry: object) -> DiscardedWindow | None:
    """Read one record back, where what is there is one.

    :param entry: One entry as the file holds it.

    :return: The record, or ``None`` where that entry is not one.
    """
    if not isinstance(entry, dict):
        return None

    host, identifier = entry.get("host"), entry.get("identifier")
    asked_for, served = entry.get("asked_for"), entry.get("served")
    noticed_at = entry.get("noticed_at")

    if not isinstance(host, str) or not isinstance(identifier, str):
        return None

    if not isinstance(noticed_at, str):
        return None

    if not _is_a_window(asked_for) or not _is_a_window(served):
        return None

    return DiscardedWindow(host, identifier, asked_for, served, noticed_at)


def _is_a_window(value: object) -> TypeGuard[int]:
    """Say whether a value read back describes a window.

    `bool` is an `int`, so a `true` would otherwise be a window of one token.

    :param value: What the file held where a window belongs.

    :return: Whether it is a whole number of tokens.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
