"""Keep the suite off the machine it is running on.

Unloading a model reaches for LM Studio's own tool, which acts on whatever
server is running. A test that forgets to intercept it evicts the developer's
model, and does so invisibly, because the caller reports the failure rather
than raising. Refusing the call here means a test cannot reach the runtime by
omission.
"""

import subprocess

import pytest

_run = subprocess.run


@pytest.fixture(autouse=True)
def _no_real_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse to run the runtime's tool, whatever a test forgot to patch."""

    def refuse(argv, *args, **kwargs):
        if isinstance(argv, list | tuple) and argv and "lms" in str(argv[0]):
            raise AssertionError(
                f"A test reached the real runtime: {list(argv)}. "
                "Patch offgrid.cli.unload, or the adapter's subprocess call."
            )

        return _run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", refuse)
