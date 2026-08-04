# offgrid

Runs a coding agent against a model held by a runtime on this machine. macOS on
Apple Silicon only. Python, managed with `uv`.

Domain language and module shape: `CONTEXT.md`. What was decided and why:
`docs/decisions.md`.

## Commands

```sh
uv run pytest                 # the suite
uv run ruff check . && uv run ruff format .
uv run ty check               # types
uv run interrogate            # docstring coverage, enforced at 100%
prek run --all-files          # everything the hooks run
```

## Agent skills

### /tdd

Seams are agreed before a test is written, and these are the ones already
agreed. Anything else needs a new agreement.

| Seam | What is tested there |
|---|---|
| `offgrid setup`, `doctor`, `run` | what a person sees and what gets launched |
| the profile file | that a hand-edited profile loads, and that older ones still do |
| a runtime adapter's parsing | a payload captured from a live server |
| a machine's sizing | what fits, at each quantization width |

Not seams: anything private. `_chosen`, `_clear`, `_let_go` and their kind are
structure, and a test against them breaks on a refactor that changed nothing.

Work one slice at a time — one test, one implementation, then the next. Not all
the tests, then all the code: bulk tests describe imagined behaviour, and they
commit to a shape before the implementation has taught anything.

A test that cannot be red is a regression guard, not a slice. Say which it is.

### /grill-me

Grill before building anything whose shape is not obvious, and record what was
settled in `docs/decisions.md` — the reasoning is the part that gets lost, and
without it a decision gets remade from memory six weeks later.

Look facts up in the environment rather than asking for them. The runtime is
running, the machine can be measured, and the git history is right there.

## Testing

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
