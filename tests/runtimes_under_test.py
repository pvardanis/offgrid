"""What a runtime adapter has to be stood in for, and which ones there are.

The conformance suite states what being a runtime means and asks it of
everything in `RUNTIMES_UNDER_TEST`. A second adapter joins by writing one of
these and adding a line here, which is the only edit it makes to the suite.

Each of these stands in below its adapter — the server it talks to, the tool it
shells out to — rather than satisfying `Runtime` with a fake. That is what
makes the suite worth running: it covers the adapter's parsing as well as its
behaviour, and the parsing is the half most likely to be wrong.
"""

from typing import Protocol

import pytest

from offgrid.domain.running.runtime import Runtime
from tests.doubles import CEILING
from tests.lmstudio_under_test import LMStudioUnderTest


class RuntimeUnderTest(Protocol):
    """One adapter, and the arrangements a suite over it needs."""

    @property
    def name(self) -> str:
        """What to call this adapter where a test says which one failed.

        :return: The runtime's name, as a profile spells it.
        """
        ...

    @property
    def address(self) -> str:
        """Where the stood-in runtime listens.

        :return: The address a person would have typed, which offgrid's errors
            about reaching it have to name.
        """
        ...

    def connect(self) -> Runtime:
        """Open a connection to the runtime that was stood in.

        :return: The adapter under test, bound to `address`.
        """
        ...

    def arrange_serving(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        holding: dict[str, int] | None = None,
        cold: dict[str, int] | None = None,
        catalogued: int = CEILING,
    ) -> None:
        """Answer as a runtime with these models, holding these of them.

        Each mapping is a model against the context it is served at once it is
        in memory. `catalogued` is what a model states before anything loads
        it, which is a ceiling rather than a window and is why the two numbers
        differ.

        :param monkeypatch: The test's patcher.
        :param holding: Models in memory, against the context each is served
            at.
        :param cold: Models it has and is not holding, against the context each
            would be served at.
        :param catalogued: What every model states before it is loaded.
        """
        ...

    def arrange_serving_regardless(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        cold: dict[str, int],
        serves: int,
    ) -> None:
        """Answer as a runtime that serves one window whatever it is asked for.

        A runtime is free to honour a window with a different one, and every
        adapter owes the same answer about which of the two it reports: what
        is being served, never what was requested.

        :param monkeypatch: The test's patcher.
        :param cold: Models it has and is not holding, against the context
            each states before anything loads it.
        :param serves: What it serves every load at, whatever was asked.
        """
        ...

    def arrange_stuck(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Answer as a runtime that will not let go of anything.

        :param monkeypatch: The test's patcher.
        """
        ...

    def arrange_taking_without_holding(
        self, monkeypatch: pytest.MonkeyPatch, *, model: str
    ) -> None:
        """Answer as a runtime that accepts a load and holds nothing.

        :param monkeypatch: The test's patcher.
        :param model: The model it takes and does not hold.
        """
        ...

    def arrange_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Answer as a runtime nothing is listening for.

        :param monkeypatch: The test's patcher.
        """
        ...


RUNTIMES_UNDER_TEST: list[RuntimeUnderTest] = [LMStudioUnderTest()]
