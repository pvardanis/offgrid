"""Where the arrangements the live checks share are registered.

Two files start a real run, and fixtures they both ask for cannot live in
either without one test module importing another. `pytest_plugins` is only
read in the conftest beside the rootdir, which is what this file is for.
"""

# The pairs first: `tests.live_runs` imports them, and a module imported
# before pytest registers it never gets its assertions rewritten — which
# pytest warns about rather than failing on.
pytest_plugins = ("tests.live_pairs", "tests.live_runtime", "tests.live_runs")
