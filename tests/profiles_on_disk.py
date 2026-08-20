"""A profile as a person types one, and as the command line builds one.

What a profile's shape refuses and what it says about the model to run are two
test modules, and both start from the same minimal file.
"""

from offgrid.agents import create_agent_config
from offgrid.domain.profile import Profile
from offgrid.runtimes import create_runtime_config

HOST = "127.0.0.1:1234"

# The whole of a minimal profile: an adapter per port, and where the runtime
# listens. `{host}` is filled in by whoever writes it.
NAMED = "runtime:\n  name: lmstudio\n  host: {host}\nagent:\n  name: claude-code\n"


def build_profile(host: str = HOST, **rest) -> Profile:
    """Build a profile the way the command line builds one.

    :param host: Where the runtime listens.
    :param rest: Whatever else the profile says.

    :return: What a run is made from.
    """
    runtime = create_runtime_config({"name": "lmstudio", "host": host})
    agent = create_agent_config({"name": "claude-code"}, runtime_host=host)

    return Profile(runtime=runtime, agent=agent, **rest)
