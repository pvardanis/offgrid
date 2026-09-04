"""The run panel's signal: a few lines, each painted by the verdict it carries.

The signal is what a person decides on, so a line that clears a run, one that
bars it, one that costs a load and one that is only a fact are told apart by
colour rather than by reading. The colours are theme variables, so they move
with the theme rather than being fixed against one palette.
"""

from textual.content import Content
from textual.widgets import Static

from offgrid.domain.costing import SignalLine, Tone

_TONE_STYLES = {
    Tone.OK: "$text-success",
    Tone.BLOCKED: "$text-error",
    Tone.COST: "$text-warning",
    Tone.INFO: "$text-muted",
}
"""How each verdict is painted: a run that is fine, barred, costed, or a fact."""


class SignalView(Static):
    """The signal lines, painted by the verdict each one carries."""

    def show(self, lines: tuple[SignalLine, ...]) -> None:
        """Paint the signal lines by the verdict each carries.

        :param lines: The signal, each line tagged with how it reads.
        """
        painted = Content("\n".join(line.text for line in lines))
        at = 0

        for line in lines:
            painted = painted.stylize(_TONE_STYLES[line.tone], at, at + len(line.text))
            at += len(line.text) + 1

        self.update(painted)

    def bar(self, said: str) -> None:
        """Show one message here, painted as a thing barring a run.

        The read that failed, or the write that did: a runtime nothing answered
        for, or a profile that would not save. It sits where the signal is,
        which is the panel a person is looking at, rather than behind the toggle.

        :param said: What to show there.
        """
        self.show((SignalLine(said, Tone.BLOCKED),))
