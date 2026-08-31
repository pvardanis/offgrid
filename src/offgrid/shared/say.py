"""How offgrid talks to whoever ran it.

Everything offgrid says goes to stderr, so that stdout carries whatever the
agent has to say and stays pipeable. A library configures no logging; this is
where the command line configures its own.
"""

import logging
import sys

import typer

LOGGER = "offgrid"


class _Stderr(logging.StreamHandler):
    """A handler that writes to stderr as it is now.

    A handler that captured the stream it was built on writes into a closed
    buffer once whoever owned that stream is finished with it, and logging
    reports that as a traceback over whatever is being read at the time.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Write a record to the stream stderr names at this moment.

        :param record: What to write.
        """
        self.stream = sys.stderr
        super().emit(record)


def say_on_stderr() -> None:
    """Print what offgrid says, as the words and nothing else.

    Only the handler this installs is replaced, because a caller that put its
    own there meant it.
    """
    logger = logging.getLogger(LOGGER)

    for existing in [h for h in logger.handlers if isinstance(h, _Stderr)]:
        logger.removeHandler(existing)

    handler = _Stderr()
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def someone_is_at_a_terminal() -> bool:
    """Whether there is anybody there to press a key.

    A screen takes the terminal and waits, so somewhere with nobody at it —
    a pipe, a file, a CI step — waits for a keystroke that is never coming.
    What is read is stdin and stderr: stdin is what a key would arrive on,
    and stderr is where a screen paints, since stdout is left to whatever
    the agent has to say.

    :return: Whether both ends are a terminal.
    """
    return sys.stdin.isatty() and sys.stderr.isatty()


def every_stream_is_a_terminal() -> bool:
    """Whether stdin, stderr and stdout are all a terminal.

    `someone_is_at_a_terminal` reads stdin and stderr: whether a person is
    there to press a key and see a screen. This adds stdout, which a screen a
    run opens at a dead end also lets go to that run's output. A redirected
    output is somebody capturing the run rather than watching it, and opening
    a screen over it would take a terminal they had already pointed elsewhere.

    :return: Whether stdin, stderr and stdout are all a terminal.
    """
    return someone_is_at_a_terminal() and sys.stdout.isatty()


def tell(message: str) -> None:
    """Say something to whoever is running offgrid.

    :param message: What to say.
    """
    typer.echo(message, err=True)
