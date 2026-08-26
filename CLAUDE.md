# offgrid

Runs a coding agent against a model held by a runtime on this machine. macOS on
Apple Silicon only. Python, managed with `uv`.

Domain language: `CONTEXT.md`. The modules, what may import what, and where a
second runtime or agent attaches: `docs/architecture.md`. What was decided and
why: `docs/decisions.md`.

`just` lists every command. `just check` is what a commit and CI both run, and
`just mutate` is the suite writing no `.pyc`, which hand mutation testing needs.

## Agent skills

**`/tdd`** — one slice at a time: one test, one implementation, then the next.
A test that cannot be red is a regression guard rather than a slice; say which
it is. These seams are agreed, and anything else needs a new agreement:

| Seam | What is tested there |
|---|---|
| `offgrid setup`, `doctor`, `recommend`, `run` | what a person sees and what gets launched |
| the profile file | that a hand-edited profile loads, which ones are refused, and that a hand edit survives being written back |
| the discarded-windows file | that a hand-edited record loads, and which ones are refused |
| a runtime adapter's parsing | a payload captured from a live server |
| a leaderboard adapter's parsing | a payload captured from the live page |
| a listing's fit | which widths a machine holds it at |
| a machine's sizing | what fits, at each quantization width |
| a live run | that a real run holds a model and lets it go — `just live` |
| `answering.py` | which error a caller gets, and what is said while it waits |
| the conformance suites | what every adapter of a port answers, not one of them |

Private names are structure, not seams: a test against `_now_holding` breaks on
a refactor that changed nothing.

**`/mattpocock-skills:code-review`** — on the branch diff before opening a pull
request, every time. It needs both axes: the fixed point (`main` for a branch
off main) and the issue the branch implements (`gh issue view <n>`, and usually
the parent).

**`/pr-review-toolkit:review-pr`** — the deeper pass, before the work goes up
for merge. Always
`code-reviewer` and `silent-failure-hunter`; add `pr-test-analyzer` when tests
changed, `type-design-analyzer` when a type was added, `comment-analyzer` when
a comment claims something about hardware or a runtime. A hook refuses to open
a pull request until it has run, since this rule was written down and missed
anyway: `OFFGRID_SKIP_PR_REVIEW=1` is how one says out loud that it does not
want a review. Pushing is left alone — work in progress is not work anyone is
proposing yet.

**`/grill-me`** — before building anything whose shape is not obvious. Record
what was settled in `docs/decisions.md`, and look facts up in the environment:
the runtime is running and the machine can be measured.

Verify every review finding before acting on it — one reviewer insisted the
fixtures' models did not exist, an hour after they were captured from a live
server. Report what a finding got wrong beside what it got right.

## Testing

- Fixtures are captured from a live runtime, never invented.
- A guard is proven by deleting it and watching the test fail.
- Errors are behaviour: assert on the message a person would read.

## Style

- Sphinx docstrings on every public module, class and function: `:param:`,
  `:return:`, `:raise:`.
- Blank lines between the steps inside a function.
- Files under 200 lines, organised by domain rather than by kind. The
  number is a prompt to ask whether a file holds two ideas; cohesion is
  what answers it. Say when a file runs past it, rather than splitting or
  cutting prose to land under it.
- Names say what a thing does, never how it is built or what it used to be.
- Comments explain why something is there. Never what it replaced.
- Fail fast, and name the operation, the input, and what to do next.

## Pull requests

Around 500 lines of diff, and one kind of change each: code, prose docs, CI,
build. What the suite enforces travels with the code — a docstring, the module
map in `docs/architecture.md`, and `source_modules` in `pyproject.toml`, the
last two guarded by `tests/test_architecture.py`. Say the split before building
it.

## Commits

Conventional Commits: `<type>(<scope>): <imperative summary>`. Subject in the
imperative, 50 characters where it fits and never past 72, no trailing period.

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`,
`ci`, `style`, `revert`. Scopes are the modules — `machine`, `fit`, `model`,
`dialect`, `profile`, `binding`, `lmstudio`, `claude-code`, `opencode`, `cli` — plus `ci`
and `deps`.

One change per commit: if the subject needs an "and", it is two. Each leaves
the suite green on its own, so a bisect lands somewhere that runs and a revert
takes back one thing. Tests go in the commit with the behaviour they cover.

A body only where the diff does not already say it: why the change was made,
and for a fix, what was reproduced. Wrap at 72, `-` for bullets. A breaking
change takes `!` before the colon and a `BREAKING CHANGE:` paragraph.

Never in a commit: what the diff states, "I" or "we", or AI attribution in the
prose. The `Co-Authored-By:` trailer stays.

## Where the work is tracked

GitHub issues on `pvardanis/offgrid`, read with `gh issue list`.
`docs/decisions.md` is for what was settled; an issue is for what was not, with
the evidence that would settle it.

## Scope

v0.1 connects one runtime to one agent and gets out of the way. Which model to
run stays a manual choice: offgrid says how much room the machine has and names
what a published list says fits it, ranked. A model catalogue, more runtimes,
more agents and a verified private mode are all later.
