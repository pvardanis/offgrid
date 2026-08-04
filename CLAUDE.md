# offgrid

Runs a coding agent against a model held by a runtime on this machine. macOS on
Apple Silicon only. Python, managed with `uv`.

## Commands

```sh
uv run pytest                 # the suite
uv run ruff check . && uv run ruff format .
uv run ty check               # types
uv run interrogate            # docstring coverage, enforced at 100%
prek run --all-files          # everything the hooks run
```

## Vocabulary

Use these words; they are what the code and its tests are named after.

- **runtime** — the server holding models in memory. LM Studio today.
- **agent** — the coding tool being launched. Claude Code today.
- **dialect** — the API shape a runtime serves and an agent expects. Mismatched
  pairs are refused, never proxied.
- **machine** — this Mac, and the memory a model may use on it.
- **held** / **resident** — a model the runtime currently has in memory.
- **launch** — an environment plus an argument list, built before anything runs.
- **profile** — what offgrid remembers between runs, in YAML, hand-editable.

## Testing

Test-driven, and test at seams agreed before writing the test: the CLI's
commands, the profile file, an adapter's parsing of a real payload. Never
against private helpers.

- One test, one implementation, then the next. Not all tests, then all code.
- Fixtures are captured from a live runtime, never invented. A test asserting
  behaviour against a fake payload tests the fake.
- A test that passes with the guard it names deleted is worse than no test.
  Check by removing the guard and watching it fail.
- Errors are behaviour: assert on the message a person would read.

When mutation-testing by hand, set `PYTHONDONTWRITEBYTECODE=1`. Edits made
within the same second as a restore leave stale `.pyc` files, and the suite
then runs against code that is no longer on disk.

## Style

- Sphinx docstrings on every public module, class and function: `:param:`,
  `:return:`, `:raise:`.
- Blank lines between the steps inside a function.
- Files under 150 lines, organised by domain rather than by kind.
- Names say what a thing does, never how it is built or what it used to be.
- Comments explain why something is there. Never what it replaced.
- Fail fast, and name the operation, the input, and what to do next.

## Scope

v0.1 connects one runtime to one agent and gets out of the way. Which model to
run is a manual choice; offgrid says how much room the machine has, and does
not recommend. A model catalogue, more runtimes, more agents, and a verified
private mode are all later.
