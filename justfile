# Commands for working on offgrid, not for using it. Running the tool is
# `offgrid setup`, `offgrid doctor` and `offgrid run`, and stays that way.
#
# `just` with no recipe lists what is here.
#
# The single checks name a hook id rather than a tool, so this file and
# .pre-commit-config.yaml cannot come to disagree about what a check is.
# `just check` is what a commit runs and what CI runs.
#
# Mutation runs go through `just mutate`: a restore landing in the same second
# as the mutation leaves a stale .pyc, and the suite then tests code that is
# no longer on disk.

default:
    @just --list --unsorted

# Install the project, its tools, and the commit hooks.
install:
    uv sync
    uv run prek install

# The suite, live checks excluded. `just test -k profile` narrows it.
test *args:
    uv run pytest {{ args }}

# The suite with coverage, failing below the floor in pyproject.toml.
cov:
    uv run pytest --cov

# Against the runtime here, which lets go of the model it is holding.
live model="qwen3-0.6b-mlx":
    uv run pytest -m live --smoke-model {{ model }}

# Every check, the way a commit and CI run them.
check:
    uv run prek run --all-files

# Formatting alone.
fmt:
    uv run prek run ruff-format --all-files

# Linting alone.
lint:
    uv run prek run ruff-lint --all-files

# Type checking alone.
types:
    uv run prek run ty --all-files

# Docstring coverage alone, enforced at 100%.
docs:
    uv run prek run interrogate --all-files

# The suite, writing no .pyc files. Use for mutation testing.
mutate *args:
    PYTHONDONTWRITEBYTECODE=1 uv run pytest {{ args }}

# Caches, not the virtualenv.
clean:
    trash .pytest_cache .ruff_cache .coverage 2>/dev/null || true
