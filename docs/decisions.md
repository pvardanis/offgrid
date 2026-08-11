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

## The module map has one home, and the rule it states is checked

The map was in two places, `CONTEXT.md` and the README, and the README's had
drifted past `speed.py`, `quality.py`, `shortlist.py` and `recommendation.py`
without anyone noticing. Two copies of a list is one copy and one lie, so it
moved to `docs/architecture.md` and `CONTEXT.md` went back to being the
glossary it says it is.

"Dependencies point inwards" had been written down since the first commit and
checked by nobody. `import-linter` states it, the hooks run it, and CI has it
through `prek run --all-files`. It is stated as two `forbidden` and
`independence` contracts rather than `layers`, because the modules are flat:
a `layers` contract needs every module named and lets a new one sit outside
every layer, which is a rule with a hole in it. A test closes the same hole
from the other side, since a module missing from `source_modules` is outside
the rule rather than passing it and `lint-imports` says nothing about it.

The one exemption, `offgrid.hold -> offgrid.runtimes.lmstudio`, is the port
that was deferred until a second adapter could show its shape. Naming it in
`pyproject.toml` makes the deferral a line that the commit building the port
deletes, rather than a paragraph nobody re-reads.

The doc describes what `hold.py` and `cli.py` consume today; it does not
declare a contract a second runtime must satisfy. That is the same reasoning
that deferred the port: an interface drawn from one implementation fits that
one, and one drawn from none fits nothing. Two parts of what is written down
are marked as LM Studio's own — the catalogue payload crossing the boundary,
and `unload` being an operation at all when a runtime that evicts for itself
would undo it.

## A port states what is wanted; the adapter owns how it is reached

`_let_go_of_the_rest` is offgrid unloading every model but the one being asked
for, one call at a time, from outside the runtime. `docs/research/adapter-surfaces.md`
read four candidates and found four different ways to reach that state: LM
Studio unloads per instance over HTTP, Ollama takes an empty request with
`keep_alive: 0`, oMLX awaits an unload and also evicts on its own against a
ceiling, and a single-model `llama-server` cannot be asked at all because the
model is the process. Orchestrating from outside works against one of the
four.

So the runtime port takes `ensure_only(identifier)` and each adapter reaches it
as it can. `let_go` stays beside it, because the end of a run is a different
question: `run` owes a release in its `finally`, by name, whatever happened.

The factory binds what does not change. `connect(host)` and `prepare(dir)`
return something satisfying a Protocol, so an address stops appearing in five
signatures and an adapter has somewhere to keep what a connection needs — LM
Studio's `instance_id`, which its unload endpoint wants and a model key does
not give.

Nothing inherits. A `Protocol` is itself a class, and what it describes is one
too, but neither is a base of the other: `ty` checks the match structurally, so
what is absent is the class hierarchy rather than the class. A connection has
identity — which server — which is the case that warrants one.

A port is a domain type and lives beside its consumer, never in the adapter
package it describes. The contract forbids the domain importing `runtimes/`,
and that covers what is inside it, so a `Runtime` declared there could not be
imported by `hold.py` without the violation this design exists to remove.

What is an attribute and what is a method is not cosmetic either. `dialect` and
`capabilities` settle when the connection opens, so they are attributes and
reading one is free. Everything that reaches the server is a method named for
what it does, so an interface says which of its members can be slow and can
raise rather than leaving that to be discovered.

Not every seam is a Protocol. A runtime and an agent each carry state and
several related members, so both are. A published list carries none and
answers two questions, so it is two typed callables kept in a record — paired
rather than registered apart, because parsing one list's payload with
another's parser is nonsense and nothing else would stop it.

A frozen dataclass holding the host, with methods, is the shape that satisfies
a Protocol here. A record of closures does not: a bare `Callable` takes its parameters
positionally and a protocol method permits them by name, so the check fails
with `parameter ... must accept keyword arguments`. Worth writing down, because
a record of closures is what gets reached for first here and the error does not
explain itself.

`Dialect` stays and `Capabilities` joins it. All four candidates serve both
dialects, so the pairing check no longer discriminates between runtimes — it
still does between agents, where Codex CLI accepts only the Responses API. What
a dialect cannot say is that LM Studio answers `200` to `count_tokens` while
logging that the endpoint does not exist. Three capabilities are carried, and
each changes what offgrid does rather than what it reports.

Adapters raise the domain's exceptions. The alternative makes the domain import
adapter modules, which the layer rule forbids and the linter catches — and
translating inside the adapter is where it belongs anyway, since Claude Code's
retry logic matches on the upstream's error wording.

Which adapters exist is an enum in the domain, beside `Dialect`, and the
registry is a dict keyed by it. Not one place, and it cannot be: an enum
carrying its own factory would be a domain type importing an adapter. So the
enum says what exists, the registry binds each name to an implementation, and
a test asserts the two agree — a forgotten registry entry fails the suite
rather than raising a `KeyError` at somebody's terminal. What this buys over a
`Literal` is that `profile.runtime` is a type at every call site; what it costs
is that the profile must be written with `model_dump(mode="json")`, because
YAML cannot represent an enum member.

A dict for the registry, not entry points and not an importable path from the
profile. The audience clones and runs, so plugin discovery serves nobody who
exists, and a dotted path in a hand-edited YAML file is an import statement in
a config file.

## Denying hosted tools is correctness; privacy is a feature that is not built

These were one thing and are now two.

WebSearch runs on Anthropic's servers. Against a model held here nothing
executes it, so the model emits the call, no executor answers, and the agent
renders the call as a result: an invented answer with no error anywhere. That
is a wrong answer, not a disclosure, and it stays denied by default. It is a
class rather than a case — Codex carries `supports_standalone_web_search` — so
the agent port answers for it, because a failure this silent will not be
noticed missing from a second adapter.

Everything else filed under privacy — nonessential traffic, telemetry, the
attribution header, the WebFetch domain check that still calls home despite
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` — becomes a feature behind a flag,
later. Naming it that way is more honest than the alternative, which is
claiming a guarantee with a known hole in it.
