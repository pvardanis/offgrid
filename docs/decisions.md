# Decisions

What was settled, and why, so it is not relitigated from memory. Newest last.

## offgrid exists to keep private work off hosted models

Company work runs on Opus; personal work that should stay private runs locally.
Privacy means content privacy: no prompt, code or file leaves the machine.
Non-content traffic — auth, update checks — is accepted, because the
alternative rules out every closed-source agent and would be a rule broken
daily. There is no fallback to a hosted model inside a private session.

## The audience is a handful of friends on Apple Silicon Macs

Clone and run. No published package, no semver, no contribution guide. Public
repo is fine; a published interface is what is deferred, because it cannot be
walked back and there is no evidence yet about what varies between machines.

## offgrid does not translate between dialects

Three of the four runtime and agent pairings need no translation. The fourth
needs a proxy, and owning a proxy's lifecycle, ports, failure modes and view of
every prompt is not worth one cell of a two-by-two. Mismatched pairs are
refused with a message naming the fix. LiteLLM already does this well if it is
ever needed.

## offgrid does not choose a model

It says how large a model the machine holds at each quantization width. Which
one to run is a person's decision, made in seconds, recorded in the profile and
overridable on the command line. Ranking installed models was built and then
removed: it rested on parameter counts parsed out of names, which is a
convention rather than a specification.

## A model is let go when the agent exits

One pool of memory, shared with everything else on the machine. The cost is a
cold load on every run — around ten seconds for a small model, twenty for a
large one — accepted in exchange for the memory sitting free between sessions.
This is why offgrid waits for the agent rather than becoming it.

## The default GPU share is an estimate, and stays one

Three quarters of unified memory, measured on one 64GB machine. Apple documents
no figure and it is reportedly lower on smaller machines, so it is optimistic
on exactly the Macs least able to afford it. Metal reports the real figure via
`recommendedMaxWorkingSetSize`, but reading it means a native dependency on a
project deliberately kept thin. Raising `iogpu.wired_limit_mb` replaces the
estimate with a value the kernel reports, which is why offgrid suggests it.

## Ports wait until there is a second adapter to extract them from

`runtimes/` and `agents/` are folders, not seams: `cli.py` imports LM Studio
and Claude Code by name, and `profile.runtime` and `profile.agent` are
validated but never dispatched on. A `Runtime` protocol was designed for this
and then deferred, because it was drawn from one implementation and would have
fitted that one. The second adapter is the thing that shows where the seam
belongs — a payload dict crossing the boundary, or the catalogue re-read after
a load, are LM Studio's problems and may be nobody else's. Protocols, a
name-to-adapter registry, and the profile fields becoming load-bearing all
arrive with it.

## The run lifecycle is not the command line's work

`hold.py` holds the model that will answer, lets go of the rest, reads back
what the runtime serves, and lets go afterwards. `launch.py` carries the launch
and starts it, passing signals on. `cli.py` keeps the commands, the arguments,
the reporting and the exit codes.

`doctor` asks what the runtime is holding, which is the question `run` asks, so
it moves too and the two stop each keeping a copy. `setup` stays where it is:
it measures a machine and writes a profile, and putting that in a module named
for holding models would be filing it under the wrong word.

This is worth doing before the ports rather than after. It invents no
abstraction and guesses at nothing — it moves code that already exists — and it
is where the search work would otherwise pile up on a file already over the
line limit.

## Progress is logged, failure is raised

The lifecycle says what it is doing through `logging`, at info, and configures
nothing. Whoever imports it decides where that goes; `cli.py` attaches one
handler to stderr with the message and nothing else, so a person sees the same
words as before. Passing a `say` callable through every function was the
alternative, and it is ceremony for something the standard library already
does, in the way an external caller already expects.

Failure travels as `OffgridError`, never as `typer.Exit`. A library that raises
its command line framework's exceptions has made that framework part of its
interface. `cli.py` turns those into a message and an exit code, which it
already did for the profile and the catalogue.

Everything a person reads goes to stderr, errors included, which they did not
before. Nothing is written to stdout yet, and that is the point: `offgrid run
-- -p "..." > answer.txt` should capture what the agent said, not offgrid
narrating over it.

## The runtime owns which models are held

offgrid asks a runtime to hold a model and to let one go. Whether a model is in
memory is the runtime's to answer, not something offgrid tracks and enforces.

LM Studio made the two look the same: nothing else manages that memory, so
offgrid asking and offgrid deciding produced the same result. oMLX does not.
It serves several models at once, evicts the least recently used, raises the
Metal wired limit at startup and enforces a ceiling of its own. Against that
runtime, offgrid unloading every model that is not the one being asked for is
offgrid doing a job already being done, to a runtime that will undo it.

So `hold` is a request and a report: ask, then say what the runtime says is
there. Confirming a model was really let go stays, because a tool that exits 0
having freed nothing is why that check exists — but it verifies an outcome
rather than enforcing one, and a runtime holding other models is not a fault to
correct.

What this costs: on a runtime that holds one model at a time, nothing. On one
that holds several, offgrid stops promising the memory is free for the model it
just loaded, because it no longer decides that.

## offgrid recommends from a published list, and still does not choose

`setup` says how large a model this machine holds. `offgrid recommend` says
which published models that size admits, ranked, so a person choosing one is
reading a list rather than remembering. It downloads nothing, and it writes
nothing to the profile: a model worth recommending is one that is not on the
disk yet, and `profile.model` naming it would make the next `run` ask the
runtime for something it does not have.

This is a separate command rather than part of `setup` because the two run on
different clocks. Memory is fixed until the machine changes; a leaderboard's
whole value is that it moved since it was last read. Folding the second into
the first puts a thing that must be re-read inside the command nobody re-runs,
and makes writing a profile depend on someone else's site being up. `setup`
ends by naming `recommend`, which is where a person is looking anyway.

The list is onyx.app's coding table, fetched as the payload their page is
rendered from. Their sibling page for hardware answers the same question and is
not used: it renders nothing server-side, and its whole filter is
`vram_int4 <= vram`, against an M1 Max it records as having 32GB. `fit.py`
measures the real figure, so it decides what fits, and `vram_int4` is ignored —
it is a parameter count times four bits, which `fit.py` already computes.

Three rules drop a row, and each says how many it dropped: no parameter count,
so it cannot be sized; no coding score, so it cannot be ranked; too large at
every width. The first takes every closed model without a word about licences,
which is fortunate, because that field holds a date on one row and nothing on a
model that has one.

When nothing survives them, the limit named is the list's and not the machine's.
The smallest model this table publishes needs about 14GB, so a 16GB Mac fits
none of it — while `docs/models.md` measures a 1.2B model on this same hardware
at 191 tok/s. "No models fit your hardware" would tell that person they can run
nothing, which is false and is the opposite of what offgrid is for. So the
message states where the list starts, what the machine has room for, and the one
fix offgrid has: the GPU wired limit, which `setup` already knows how to suggest
and now suggests from the same place.

One row that fits is stated rather than ranked. A leaderboard filtered down to a
single model is not a ranking, and framing it as one would say the rows that are
gone had been beaten rather than dropped.

The quality figure keeps the shape of theirs — memory headroom, a score, speed,
context window, out of 97 — with one term replaced. Theirs ranks a model by
percentile within what fits, needs six populated benchmarks and five ranked
models to compute either, and has an empty fallback map, so on a Mac it is the
constant 50 for everything and the term reduces to a reward for having more
active parameters. Substituting the published SWE-bench figure makes the column
mean what it says. It also reverses the order: the dense 27B leads their table
for being dense.

Speed is derived here rather than taken from the table. Their figure is a
hosted GPU's and does not move with quantization width; their formula divides
bandwidth by the whole of the weights, which is right for a dense model and
reads all 35B of a 3B-active one. `docs/models.md` measured both cases on this
machine, and its constants — 60% of peak bandwidth dense, 21% for a MoE with
few active parameters, over the weights actually read per token — land within
about a tenth of every figure recorded there. The cost is a table of bandwidth
per chip, which offgrid did not need before; a chip missing from it means no
speed figure for that row rather than a wrong one.

Nothing is printed without saying where it came from: the table's own date, and
that nobody independent produced any of it. What is not claimed is that the
numbers are the vendors' own. That was established for the two models that fit
this machine, by hand, and it lives in `docs/models.md` where a person wrote it,
not in a line generated from a table where it would be a guess about the other
twenty-five.

The last good table is cached beside the profile so an unreachable site
degrades to a stale answer with its date shown. No copy is committed. Fetching
is what their robots.txt permits and names AI crawlers to permit; whether the
table may be redistributed is stated nowhere, and a copy in a public repository
is the one form of use that would need it to be. A committed table would also
be stale on the day it was cloned.

## A kept table answers when a current one cannot, and says how old it is

`recommend` reaches the network every time it runs, and the machine it runs on
may not have one. So the last payload that parsed is kept beside the profile
with the day it was read, and answered from when nothing else can. There is no
expiry and no refresh flag: running the command again is the refresh.

Both failures fall back, both say why, and the reason is what differs. A site
that did not answer is ordinary, and the sentence names the network so nobody
goes looking for a fault on a machine whose other three commands need none. A
page that answered and no longer parses names the URL and what was looked for,
because that is the maintainer's to fix, and a silent fall back to a table
months old is the feature dying without anyone noticing. Neither is quiet about
age: how old what is shown is gets printed either way.

Only a payload that parsed is kept. Keeping one that did not would take the
fall back away at the moment it is all the command has left. A kept payload
that no longer parses counts as none, because offgrid's own file failing to
read back is not a second thing to explain to somebody already being told the
site is unreachable.

Which of the two tables is answered from is `leaderboards/reading.py`'s, and it
returns the lines saying so rather than printing them, as `recommendation.py`
does. The adapter beneath it owns fetching and parsing one list and knows
nothing of a fall back; `leaderboards/cache.py` owns the file and names no
list, so a second list reuses it as it is.
