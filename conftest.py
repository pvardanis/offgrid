"""Where the arrangements the live checks share are registered.

A fixture two test modules ask for cannot live in either without one of them
importing the other. `pytest_plugins` is only read in the conftest beside the
rootdir, which is what this file is for.
"""

pytest_plugins = ("tests.live_runtime", "tests.live_runs")
