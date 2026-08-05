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
| a live run | that a real run holds a model and lets it go — `pytest -m live` |
| `hold.py` | which error a caller gets, and what is said while it waits |

Not seams: anything private. `_now_holding`, `_let_go_of_the_rest` and their
kind are structure, and a test against them breaks on a refactor that changed
nothing.

Work one slice at a time — one test, one implementation, then the next. Not all
the tests, then all the code: bulk tests describe imagined behaviour, and they
commit to a shape before the implementation has taught anything.

A test that cannot be red is a regression guard, not a slice. Say which it is.

### /pr-review-toolkit:review-pr

Run it on the branch diff **before pushing a pull request**, not after opening
one. Findings arriving after review has started waste the reviewer's pass.

Which agents apply here: `code-reviewer` and `silent-failure-hunter` always;
`pr-test-analyzer` when tests changed; `type-design-analyzer` when a type was
added; `comment-analyzer` when a comment claims something about hardware or a
runtime's behaviour.

Verify every finding before acting on it. Reviewers state falsehoods with the
same confidence as truths — one insisted the models in the fixtures did not
exist when they were captured from a live server an hour earlier. Reproduce the
failure, then fix it. Report what a finding got wrong alongside what it got
right.

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

## Where the work is tracked

GitHub issues on `pvardanis/offgrid`, read with `gh issue list`. What is
deferred and why belongs in one, alongside the evidence that would settle it —
a decision recorded nowhere outlives the session that made it.

`docs/decisions.md` is for what was settled. Issues are for what was not.

## Commits

Conventional Commits: `<type>(<scope>): <imperative summary>`. Subject in the
imperative, 50 characters where it fits and never past 72, no trailing period.

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`,
`ci`, `style`, `revert`. Scopes are the modules — `machine`, `fit`, `model`,
`dialect`, `profile`, `lmstudio`, `claude-code`, `cli` — plus `ci` and `deps`.

A body only where the diff does not already say it: why the change was made,
and for a fix, what was reproduced. Wrap at 72, `-` for bullets. A breaking
change takes `!` before the colon and a `BREAKING CHANGE:` paragraph.

One change per commit. If the subject needs an "and", or the type is not
obvious from the diff, it is two commits: a fix and the housekeeping it sat
next to, a refactor and the defect found while moving the code. Each one
leaves the suite green on its own, so a bisect lands somewhere that runs and
a revert takes back one thing.

Tests go in the commit with the behaviour they cover, not in a commit of
their own.

Never in a commit: what the diff states, "I" or "we", or AI attribution in the
prose. The `Co-Authored-By:` trailer stays.

## Scope

v0.1 connects one runtime to one agent and gets out of the way. Which model to
run is a manual choice; offgrid says how much room the machine has, and does
not recommend. A model catalogue, more runtimes, more agents, and a verified
private mode are all later.
