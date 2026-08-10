"""The last published list offgrid read, kept for a run that reaches none.

A leaderboard's value is that it moves, and the machine it is read on may be
on a plane. So the payload is kept exactly as the source answered it, beside
the profile, and re-read when nothing answers. There is no expiry and no
refresh flag: running the command again is the refresh.

Nothing here knows which list it holds, and a payload that cannot be read
back is no cache rather than an error — this is offgrid's own file, and a run
that cannot reach the network has enough to say already.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# What the file calls each of the two things it holds.
PAYLOAD = "payload"
FETCHED = "fetched"


@dataclass(frozen=True)
class Cached:
    """A payload as a source answered it, and when it was asked.

    :param payload: What came back, verbatim, so that whatever parsed it once
        parses it again.
    :param fetched: When offgrid asked, as ``2026-08-10T14:31:07``. What the
        list says about its own age is the list's to state; this is offgrid's
        record of when it last saw it.
    """

    payload: str
    fetched: str

    @property
    def dated(self) -> str:
        """The day it was fetched, which is as fine as anyone reads one.

        :return: The date, as ``2026-08-10``.
        """
        return self.fetched.split("T")[0]


def remember(payload: str, path: Path) -> None:
    """Keep a payload that was read, replacing whatever was kept before.

    :param payload: What the source answered.
    :param path: Where to keep it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            {PAYLOAD: payload, FETCHED: datetime.now().isoformat(timespec="seconds")}
        )
    )


def recall(path: Path) -> Cached | None:
    """Read back the last payload kept, if there is one to read.

    :param path: Where it would have been kept.

    :return: What was kept, or ``None`` where nothing was, or where what is
        there is not what this wrote. A file offgrid cannot read back is one
        it will overwrite on the next good fetch, so it is worth no message.
    """
    try:
        kept = json.loads(path.read_text())
    except (OSError, ValueError):
        return None

    if not isinstance(kept, dict):
        return None

    payload, fetched = kept.get(PAYLOAD), kept.get(FETCHED)
    if not isinstance(payload, str) or not isinstance(fetched, str):
        return None

    return Cached(payload=payload, fetched=fetched)
