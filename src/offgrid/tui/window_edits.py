"""What windows a person set this session, and which row is being edited.

The picker floats the window slider over one model row at a time. This holds
the two facts that outlive a single float: the window each model was set to for
the length of the session, and which model the open slider is editing — so the
committed window is recorded against the row it was opened over rather than
wherever the highlight has since moved.

The mapping is what a run is priced at and what each row shows, handed to the
domain that reads a requested window; the picker keeps this beside the report
and reaches into it as the report is recomputed.
"""


class WindowEdits:
    """The windows set this session, and the model the open slider edits.

    A window is not recorded until the slider commits, and it is recorded
    against the model the slider was opened over — so arrowing to another row
    while the slider is open cannot land the window on the wrong model. An
    abandoned edit records nothing.
    """

    def __init__(self) -> None:
        """Start with no windows set and no row being edited."""
        self._windows: dict[str, int] = {}
        self._editing: str | None = None

    @property
    def windows(self) -> dict[str, int]:
        """What each model was set to this session, keyed on the model.

        :return: The windows, as the domain that prices a run and the row that
            shows one both read them. Empty where nothing was committed.
        """
        return self._windows

    def begin(self, identifier: str) -> None:
        """Note which model the slider is now editing.

        :param identifier: The model the slider was floated over, which a later
            commit records the window against.
        """
        self._editing = identifier

    def commit(self, window: int) -> str | None:
        """Record the window for the model being edited, and close the edit.

        :param window: The window the slider settled on, already refused where
            the model could not hold it.

        :return: The model the window was recorded against, so the picker can
            redraw that row, or ``None`` where nothing was open to record it —
            a commit with no edit begun, or a second commit after one.
        """
        identifier = self._editing
        self._editing = None

        if identifier is None:
            return None

        self._windows[identifier] = window

        return identifier

    def cancel(self) -> None:
        """Abandon the open edit, so a following commit records nothing."""
        self._editing = None
