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

`answering.py` decides which model will answer and asks the runtime to hold it.
Letting go of the rest, reading back what the runtime serves, and letting go
afterwards moved behind the runtime port with the rest of the mechanism — what
stays here is the decision. `launch.py` carries the launch
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

Which table is answered from is `domain/sizing/reading.py`'s, and it returns the
lines saying so rather than printing them, as `recommendation.py` does. The
adapter beneath it owns fetching and parsing one list and knows nothing of a
fall back; `domain/sizing/cache.py` owns the file and names no list, so a second
list reuses it as it is.

## A list that will not answer is passed over before a stale one is read

The registry holds the published lists in the order they are asked, and the
first with a table answers. What was kept is reached only when none of them
did, because a current table from a list further down beats one read a
fortnight ago — the fall back exists for the machine with no network, not for
the site that is down this morning.

So a second list buys redundancy, and that is the whole of what it buys.
Merging two into one ranking is a different question: `Listing.coding_score` is
onyx's `swe_bench_verified`, and a list scoring on something else makes the
rows incomparable. Which is why the list that answered is named whenever it was
not the first — the figures below are somebody else's, and that decides whether
they can be read against what was seen last week.

The registry is an ordered tuple rather than a dict keyed by an enum, which is
where it parts company with the runtime and the agent. Theirs are enums because
a profile carries a hand-typed name and the enum is what refuses a typo when
the file is read. Nothing names a published list, so an enum here would be a
key nobody looks up, and `reading.py` indexing one by name would be the
coupling this seam removes. Order is the only thing the registry has to state.

One kept payload serves every list, because a parser refuses a payload that is
not its own and the table it answers with names its own source. Reading a kept
one back by offering it to each list in turn therefore attributes it correctly
with no name to key on — which is the other thing a per-list name would have
been for.

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

The doc describes what `answering.py` and `cli.py` consume today; it does not
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

So the runtime port takes `ensure_only(identifier, window)` and each adapter
reaches it
as it can. `let_go` stays beside it, because the end of a run is a different
question: `run` owes a release in its `finally`, by name, whatever happened.

The factory binds what does not change. `connect(host)` and `prepare(dir)`
return something satisfying a Protocol, so an address stops appearing in five
signatures and an adapter has somewhere to keep what a connection needs — the
host every call to LM Studio carries, and the capabilities settled when it
opened.

Nothing inherits. A `Protocol` is itself a class, and what it describes is one
too, but neither is a base of the other: `ty` checks the match structurally, so
what is absent is the class hierarchy rather than the class. A connection has
identity — which server — which is the case that warrants one.

A port is a domain type and never lives in the adapter package it describes.
The contract forbids the domain importing `runtimes/`, and that covers what is
inside it, so a `Runtime` declared there could not be imported by `answering.py`
without the violation this design exists to remove.

Each port gets its own module — `runtime.py`, `agent.py`, `leaderboard.py` —
rather than being declared inside whatever calls it. A contract nobody can find
is one the second adapter gets written without, and the module map is how this
repo says where things are. It costs a `runtime.py` one letter from
`runtimes/`, in the one file that imports both.

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

The registry sits in the package's `__init__.py` and nothing else is exported
beside it. A re-exported `LMStudio` would read the same to `import-linter` as
the `RUNTIMES` import `cli.py` legitimately makes, since it reads statements as
written — so the rule that only a registry may import a concrete adapter would
stop being checkable. Re-exports curate an API, and there is no published one
here to curate.

A dict for the registry, not entry points and not an importable path from the
profile. The audience clones and runs, so plugin discovery serves nobody who
exists, and a dotted path in a hand-edited YAML file is an import statement in
a config file.

The profile stops carrying the machine it was written on. `chip`,
`memory_bytes` and `wired_limit_bytes` were written by `setup` and read by
nothing, since `setup` and `recommend` each measure where they need it, and
keeping them invites sizing from a number recorded weeks ago. A GPU limit is
not stable: a reboot drops it back to its default and a runtime may raise it as
it starts, so read at the point of use it is right for every runtime rather
than one. `setup` keeps measuring and printing — that is what it is for. A
profile still carrying the fields is refused by name rather than migrated,
because the message already says to run `setup` again and thirty seconds of
re-running beats a shim that outlives the files it was written for.

## What building the runtime port settled

Three things the design could not have known, found while it was built.

**A protocol attribute is declared as a property, or nothing frozen satisfies
it.** Written `dialect: Dialect`, the member is one a caller may also assign
to, and `ty` refuses the pair: `protocol member capabilities is incompatible —
the member does not accept writes`. Declared with `@property` it is read-only,
a frozen dataclass field satisfies it, and a caller still reads
`runtime.dialect`. `Agent` is declared the same way for the same reason.

**The release owed after a failed load lives in the adapter.** The domain
cannot see whether a load was attempted, so a `hold_model` that let go of what it
was asked for would fire a release at a name the runtime does not have — noise
on the likeliest mistake there is, a typo in a model name. The adapter knows
which of its own calls may have taken weights, and wraps that one.

**`held` no longer names the address it could not reach.** The port carries a
dialect and capabilities and not a host, on purpose: what a connection is bound
to is its own business. So "The runtime at 127.0.0.1:1234 is holding no model"
became "The runtime is holding no model", and the address stays in the errors
the adapter raises, which is every other one. What it costs is real: this
message is the one `doctor` prints when nothing is held, and `doctor` fails
before it prints the address, so on that path the address is nowhere. What it
buys is that a `Runtime` is not made to expose an address for a sentence, which
every adapter after this one would have paid for.

## What building the agent port settled

**The guard answers for a configuration that is not there.** Splitting the
write from the check leaves a caller free to ask the check on its own, and a
directory with no settings file in it denies nothing. So absent settings are
refused in the guard's own words, naming the file, rather than surfacing as a
traceback from a read that assumed `configure` had run.

**Where an agent keeps its configuration follows the name it was looked up
by.** A directory named for one adapter, reached through a registry keyed by
name, is a directory the second adapter inherits. It sits beside the profile,
under the name the profile carries, which is where `recommend` already keeps
the table it cached.

**Turning a profile into an adapter belongs to the registry package.** Review
asked for it in `runtime.py` and `agent.py`, beside the ports, so the command
line would hold two functions rather than two registry lookups. The functions
are right and the address is not: a port is a domain module, and a domain
module reaching a registry is the violation these seams exist to remove.
`lint-imports` reports it as `offgrid.runtime is not allowed to import
offgrid.runtimes`, and it spreads — `profile.py` imports the port for its enum,
so it fails too. A port taking a `Profile` is also a cycle, since `profile.py`
imports the port back. So `connect_runtime` and `prepare_agent` sit in
`runtimes/__init__.py` and `agents/__init__.py`, one layer out, where reaching
the domain is what an adapter is allowed to do.

## The module that decides is named for the decision, not for the mechanism

`hold.py` was named for what it did before the port: hold a model, let go of
the rest, read back, let go afterwards. Three of those four moved behind
`Runtime`, and what was left was the decision — which model answers — under a
name that promised the mechanism.

It also held `hold` and `held`, two letters apart, one asking and one acting,
and the command line put both in one expression. `CONTEXT.md` already carries
`resident` as the word for a model in memory, so the asking one takes it and
says it fetches: `get_resident_model`.

`hold` stays as the domain's word, in the glossary and in `hold_model`. It was
a word the README used and the language never defined, which is how it ended up
naming a module that had handed its mechanism away. Defined, it is the act this
project needs a word for — make this the resident model, whatever that costs
the runtime. Both functions say what they act on, so a call site reads as an
action rather than as a value.

The rule that a run naming no model wants whatever is resident moved out of
`cli.py` and into `hold_model`. It is a domain rule, it was a ternary, and moving it
gives the function something to decide rather than a call to forward.

## Denying hosted tools is correctness; privacy is a feature that is not built

These were one thing and are now two.

WebSearch runs on Anthropic's servers. Against a model held here nothing
executes it, so the model emits the call, no executor answers, and the agent
renders the call as a result: an invented answer with no error anywhere. That
is a wrong answer, not a disclosure, and it stays denied by default. It is a
class rather than a case — Codex carries `supports_standalone_web_search` — so
the agent port answers for it, because a failure this silent will not be
noticed missing from a second adapter.

What "denied by default" covers is the configuration offgrid writes, a
hand-edited one that undoes it, and the arguments that decide whether either is
read. `offgrid run` hands everything after `--` to the agent, and one of those
arguments reaches the tool past a settings file that denies it. Which one, and
why it is the only one, is the entry below.

Everything else filed under privacy — nonessential traffic, telemetry, the
attribution header, the WebFetch domain check that still calls home despite
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` — becomes a feature behind a flag,
later. Naming it that way is more honest than the alternative, which is
claiming a guarantee with a known hole in it.

## Only one argument gets past the deny, and it is refused

#65 asked which of the arguments Claude Code takes could undo the WebSearch
deny, having read them out of `--help`. `--help` says what a flag is for, not
how it composes with a deny, so the question was answered by measurement:
`ANTHROPIC_BASE_URL` pointed at a proxy in front of the runtime, which logged
the `tools` array of every request, and each flag was run against a model held
on this machine. What the model then said was not evidence — a local model will
narrate a tool call whether or not it was offered one — so the tool list the
agent sent is what was read. Against claude 2.1.231:

| After `--` | WebSearch offered |
|---|---|
| nothing | no |
| `--dangerously-skip-permissions` | no |
| `--permission-mode bypassPermissions` | no |
| `--allowedTools WebSearch` | no |
| `--settings` carrying `permissions.allow` | no |
| `--setting-sources user` | no |
| `--setting-sources project,local` | **yes** |
| `--setting-sources=project,local` | **yes** |
| `--setting-sources user --setting-sources project,local` | **yes** |
| `--setting-sources project,local --setting-sources user` | no |

Four of the five suspects are innocent. `deny` is applied where the tool list
is built, so a denied tool is never offered, and nothing that turns a
permission check off can put back a tool the model was not given. An `allow`
loses to a `deny` rather than merging past it. The one that works does not
touch permissions at all: it stops the file being loaded. offgrid writes the
`user` source, and a list of sources omitting `user` never reads it.

The last two rows are why the last of those arguments is the one read, rather
than the first. Claude Code takes the later value when given the flag twice,
so stopping at the first match would pass the one line that drops the deny and
refuse the one that does not.

So the adapter reads the arguments alongside the settings, and a run that
could reach the tool is refused rather than warned about: the failure is
silent, and a warning scrolls off the top of a session that then runs for an
hour — the same silence this exists to break. Only that one argument, because
refusing the other four would cost someone a run to prevent nothing.

The arguments are read where the settings are read, rather than in a member of
their own. The two halves answer one question — is this run going to invent
answers — and neither answers it alone. Neither can go in `plan`, which runs
after the model is held: a refusal there wastes the one wait in the program
that nobody gets back.

The answer is version-specific. It was measured, not read, and a later Claude
Code could apply `deny` somewhere else. What protects that is the table above:
re-run it and see, rather than trusting the tests, which encode the finding
rather than checking it.

## The agent answers; offgrid decides

`require_hosted_tools_denied` was a member of the agent port that raised. It is
now two things: `read_hosted_tools` on the port, answering with a
`HostedToolsReport`, and `require_hosted_tools_denied` in `hosted_tools.py`,
which takes that report and raises. `dialect.py` already had this shape —
`agent.dialect` states a fact, `require_compatible` decides it is a problem,
`cli.py` calls it — and this is the same split for the same reason.

Three things follow from it, and the third is why it was worth doing.

`doctor` can report what `run` refuses. #64 asked for a line beside the other
four, and a member that raises cannot give one: two of the states — a
configuration that permits the tool, and no configuration yet — raise the same
exception, so telling them apart meant matching on the message. A reading with
four states says which, and each command decides what that means. `run` refuses
on `PERMITTED`; `doctor` prints and exits 0. `UNWRITTEN` never reaches `run`,
because `configure` has written the file by then, which is what made that state
awkward to word while the guard was the only caller.

The policy stops being adapter business. Which tools are hosted, what the
configuration says, and which arguments stop it being read are things only the
adapter knows. That a reachable one stops a run is offgrid's rule, and a
guarantee holding for one agent and not another would tell a person nothing.
The words in the refusal are still the adapter's — the report carries its own
`detail` and `remedy`, so the message a person reads names their file or their
flag exactly as before.

And an agent with no hosted tool has something true to say. opencode 1.18.14
offers ten tools — bash, edit, glob, grep, read, skill, task, todowrite,
webfetch, write — and every one runs on this machine; it speaks to whatever
provider it is pointed at rather than to one vendor, so there is nothing
server-side to deny. Measured the same way as the Claude Code table above, by
reading the tool list it sends. Under a member that raises, its adapter would
implement a guard whose body does nothing, indistinguishable from an adapter
whose author never considered the question. Under a reading it answers
`NONE_OFFERED`, which is a dated fact with evidence behind it.

The reading writes nothing and changes nothing. Rewriting a settings file would
overrule an edit someone made deliberately, and dropping an argument would
launch something other than what they typed — both are the silent divergence
this whole area exists to prevent, committed by the thing meant to prevent it.
So the remedy it carries is words.

## An adapter is bound to what a run has already settled

`ClaudeCode` took a directory and was handed the arguments twice — once to
check them, once to build a command line from them. Nothing made those the same
arguments; `cli.py` passed one variable, but the types allowed a later edit to
check one thing and launch another, which is exactly the hole the check exists
to close.

Both are settled before a run starts, so the adapter is bound to both:
`Prepare` takes the directory and the arguments, and `plan` takes only the
model, which is the one thing the run discovers. `doctor` binds with no
arguments, and so reports on a configuration alone — which is all it can
honestly speak to, since nobody types a command line for a run they have not
made yet.

The same rule settles `host` and `token` when there is a second agent to draw
it from: bind what the profile and the command line have already fixed, pass
what the run produces.

## What persists and what is true of one run

`configure` takes nothing, writes to disk, and depends only on what is already
in the directory — it is about the place the agent lives. `plan` takes this
run's facts, writes nothing, and answers with a value describing one launch —
it is about the occasion. That axis is why reading what a run could reach is a
third call rather than folded into either: it reads the settings file, which is
the place, and the arguments, which are the occasion, and a check spanning both
cannot live in a member that owns one.

Four other homes were tried and each gives up something the axis explains.

A second protocol, so an agent with nothing hosted implements nothing, makes a
forgotten reading indistinguishable from a legitimate absence — `cli.py` would
skip both silently, which is the failure the slot exists to prevent, one level
up. `plan` cannot: it runs after the model is held, so a refusal there wastes
the one wait in the program nobody gets back, and it would stop being pure —
ten tests build a launch against a directory nothing has written yet.
`configure` cannot: it would gain a parameter changing nothing it writes, and
one call would both preserve a person's edit and reject it. `__init__` cannot,
and this one is structural rather than a trade: `ClaudeCode` writes the
settings file it would validate, so checking at construction means never being
able to bootstrap a machine that has not run yet.

What the argument turned up in passing is that offgrid has this shape already.
`agent.dialect` states a fact, `require_compatible` decides it is a problem,
`cli.py` calls it — and the reading is the same three parts for the same
reason.

## A profile grows a section per adapter

`host` sat flat beside `runtime` as though it were global, and there was
nowhere for an adapter's own settings to go — which the second agent needs
immediately, since opencode learns where the runtime listens from a
`provider.<name>.options.baseURL` block in a file it must be configured with,
rather than from an environment variable at launch.

So the profile nests: `agent: AgentConfig` and `runtime: RuntimeConfig`, each
carrying a `name` and whatever else that adapter reads, with `host` moving
under the runtime that is the only thing it means anything to.

Two findings shape how, and both were measured rather than reasoned.

Pydantic will not parse a base-annotated field into a subclass. Annotate
`agent: AgentConfig` and a section holding an adapter's own keys either has
them silently dropped or is refused outright, depending on `extra` — never
parsed into the subclass that declares them. Only the shapes that tell the
parser which class to build work: a discriminated union, which would make
`profile.py` import every concrete config, or something that picks the class
before pydantic is asked.

So nothing parses a profile in one step. The file is read as a mapping, each
registry is asked to build its own section into the config its adapter
declares, and the profile is constructed from the two finished configs. That
is the shape `aily` uses — a builder holding injected factories, a raw dict in,
concrete configs out, and the discriminator stripped before construction — and
it is why its parent config can annotate an abstract base at all.

A config's `name` is therefore a `@computed_field` property, abstract on the
base and answered by each adapter, rather than a field a file sets. Which class
a profile gets is the registry's answer to the name in the file; once built,
the class is the authority on what it is, which is what lets `connect_runtime`
and `prepare_agent` look up by the config's own name. Computed rather than
plain, because a plain property is left out of `model_dump`, and a profile
saved without `name:` would silently load as whichever adapter is the default.

And the port cannot take a `Profile`: `profile.py` imports `AgentName` from
`agent.py`, so the reverse is a cycle. That is the right way round anyway — a
port taking the config-file type has made the file format part of its
interface, and every adapter would see fields that are none of its business.

The configs live in `agent.py` and `runtime.py` beside the vocabulary they
belong to, not in a `config/` folder, which would group them by kind and split
each adapter's knowledge across two files.

The registry stays a closed enum keyed dict, which is not open for extension:
adding an adapter edits the enum and the registry both. That is deliberate. The
alternative is self-registration, and it costs the property that `agents/` is
the one place a name becomes an adapter — checkable by reading imports, which
is what #56 is about — along with the validated set that lets a profile refuse
an unknown agent at load rather than at dispatch.

There are two dicts per port rather than one, keyed alike: a name becomes a
config, and a config becomes an adapter. The config dict is typed
`type[AgentConfig]`, which is covariant, so it names the concrete class. The
factory dict is typed on a callable taking the base, and callable parameters
are contravariant, so a factory declared to take a concrete config cannot sit
in it — each takes the base and narrows inside, raising where it was handed
another adapter's. Pairing each config type with its factory in a generic
holder, so a cross-wiring is a type error where it is written, was considered
and set aside as more machinery than two adapters justify.

`plan` ends up taking only the model, which is the one thing a run discovers.
Where the runtime listens rides on the agent's config as `runtime_host`, filled
from the runtime's section while the profile is built and excluded from what is
written back — the file says it once, under the runtime it belongs to, and an
agent that writes the address into a config file of its own has it before
`configure` runs. Filled there rather than set afterwards because a config is
frozen, and because a step the command line has to remember is a step it can
forget: a missed one would write no address at all and fail as a model that
cannot be reached. The directory an agent is run out of is derived from its own
name, so it is neither said nor passed. The token went into
`agents/claude_code/`: the local server ignores it and Claude Code refuses to
start without one, which makes it a fact about that agent rather than the run.

What a validator refused is passed through as pydantic wrote it, rather than
condensed into a phrase. It costs a reader six lines, a class name and a URL
where one line would have named the field — and buys one fewer thing to keep
true, since a hand-rolled summary drifts from what the validator actually
checked. Taken deliberately, with both messages read side by side.

A bad adapter key says to fix it by hand and stops there, where every other
profile error offers `offgrid setup` as well. `setup` would answer it, but
lossily: the file no longer loads, so it is set aside as `.yaml.rejected` and a
fresh profile is written from the defaults, losing the address and the model
along with the bad key. A one-line edit is the better instruction, so that is
the one given.

A profile in the flat shape is refused rather than migrated, naming the shape
it now wants. v0.1 is a handful of people on a clone-and-run project, and a
silent rewrite of a hand-edited file is worse than a clear refusal.

Two guards are written deliberately, because each protects against a silent
failure rather than a visible one: that every concrete config forbids the keys
it does not name, and that every name in each enum has both an adapter and a
config factory behind it. Both were proven by breaking them.

Reading and building are two calls, because `profile.py` may not name an
adapter and only the command line has both registries. `load_yaml` answers with
the mapping, each registry answers with its own config, and `create_profile`
puts them together — passing the rest of the body whole, so a key belonging to
no section is still refused rather than quietly dropped. `Capabilities` moved
out of `runtime.py` into `capabilities.py`, and `OFFGRID_HOME` into `home.py`,
which two modules that may not import each other both need.

## The tree says what the layers are

Twenty-odd modules sat at the root of `src/offgrid/`, and which layer each
belonged to was visible only in `docs/architecture.md`. A module landed
wherever it was written, and the map was the only thing that said otherwise —
which made the map something to keep true rather than something to read.

So the layers are folders: `domain/`, `shared/`, and the adapter packages that
were already there, with `cli.py` alone at the root because it is the only
thing outside all of them.

What this buys is not tidiness. The contract saying the domain knows nothing
about adapters was stated over every domain module by hand — twenty names, and
a new module was covered only if somebody remembered to add it. It is stated
over `offgrid.domain` now, and everything beneath it is covered by being
beneath it. The test that closed the same hole from the other side shrank with
it: it places a module by the first package above it that a layer claims,
rather than matching names one at a time.

A third contract was written while moving, because the move showed it was
missing. `shared/` claims to reach nothing of offgrid's own, and nothing said
so: `home.py` and `declaring.py` had been named in the domain contract and
stopped being, while `say.py` had never been covered at all. Probed one module
at a time, three of the four were caught anyway through something that imports
them, and `say.py` was not caught by anything. The claim is a contract now
rather than a sentence.

`shared/` is what reaches nothing of offgrid's own, and that is a test rather
than a description: `exceptions.py`, `say.py`, `home.py` and `declaring.py`
each import only the standard library or a dependency. `home.py` in particular
stops being a module of its own for want of anywhere else — `agent.py` derives
an agent's directory from it and `profile/` needs it for the file, and
`profile/` already imports `agent.py`, so it could live in neither.

`domain/` rather than `ports/` for the two seam modules, and rather than a
package each. A package holding one file says nothing, and `runtime/` beside
`runtimes/` would have been two folders one letter apart — the cost this file
recorded as worth paying when one of them was a file. As `domain/runtime.py`
beside `runtimes/`, it stops being a cost at all.

It is a move: no behaviour changes, and every test that was there passes
against the same code at a different address. `tests/test_architecture.py` is
the exception and had to change, since what it checks is where things are.

## What fits and what runs do not know each other

`domain/` was fifteen modules and a package, and read as a graph it was already
two clusters with no import between them in either direction. The code had the
boundary and did not say so.

```
fit · listing · speed · quality · shortlist · recommendation -> machine, each other
model · dialect · capabilities · hosted_tools · launch · runtime · agent · answering
```

Not one edge crosses. It falls out of what the commands do: `recommend` draws
entirely from the first, `doctor` and `run` entirely from the second, and
`setup` straddles both, which is what a composition root is for.

So they are `sizing/` and `running/`, named for the question each answers. The
folders are the smaller half of it. The point is the contract, because the two
being disjoint was true by accident and nothing protected it — an import from
`quality.py` to `model.py` would read as reasonable in review and would fuse
the halves in silence. Proven by writing that exact import and watching
`lint-imports` refuse it.

`profile/` stays a sibling rather than moving under `running/`, though it
imports `agent` and `runtime`. It is what offgrid remembers between runs —
what a run is made from, not part of making one, and `setup` reads it without
running anything. It also has to sit outside the contract, since it depends on
one of the two halves; folding it in would muddy what the contract asserts.

The two ports moved with it: `runtime.py` and `agent.py` are under `running/`
now, so the note above about `domain/runtime.py` sitting a folder from
`runtimes/` reads as `domain/running/runtime.py`, two folders from it. The
names stay close — `running/` and `runtimes/` — but never at the same level,
which is what made the old pair worth paying down.

`running/` rather than `run/`, which was the other candidate. `run` is the
noun offgrid uses everywhere and is truer to the ports — `agent.py` runs
nothing, it says what offgrid asks of an agent — but the gerund pairs with
`sizing/`, and the pair reads as the question each half answers.

## Choosing between adapters is policy, and policy is the domain's

`reading.py` decided which published list answers, and did it from inside
`leaderboards/` — importing that package's own registry. Every other seam
splits the same job the other way: `answering.py` is a domain module and is
handed a `Runtime`, and `cli.py` is where the registry and the policy meet.

The difference was invisible to the check that exists for it. The contract
forbids `offgrid.domain` importing an adapter package, so a domain module
reaching a registry fails `lint-imports` — and an adapter module doing it does
not, because it is already on that side of the line. Coupling caught in one
place and unremarked in the other is the shape of a rule that has stopped
covering the thing it was written for.

So `reading.py` moved to `domain/sizing/`, beside the port it reaches for, and
takes the lists as an argument. `cli.py` hands it `LEADERBOARDS`. `cache.py`
moved with it: it names no list, it keeps what offgrid remembers between runs,
and `domain/profile/profile.py` already owns a file on exactly those terms —
`shared/` would have filed a domain concept under the word for cross-cutting
helpers.

Proven the way the domain split was: by restoring the import and watching
`lint-imports` refuse it with `offgrid.domain is not allowed to import
offgrid.leaderboards`.

What this leaves is three seams of one shape. `leaderboards/` holds published
lists and the registry naming them, as `runtimes/` and `agents/` hold theirs,
and the command line is the only module in the tree that imports any of the
three.

## Binding a run is its own module, and the command line is not it

`read_profile` was public in `cli.py`, and `tests/test_profile.py`,
`tests/test_live.py` and `tests/test_cli.py` all imported it from there.
Nothing chose that: the function needs both registries, `cli.py` had them, and
the module a thing lives in became the interface everything else reaches
through. `binding.py` takes it and `bind_run` beside it, and joins the
command-line layer.

`tests/test_profile.py` carried a defence of the old arrangement — that the
command line is the one place with both registries. It was weighed and found
descriptive rather than load-bearing: nothing stops another module holding both,
since the rule forbids reaching *past* a registry to a concrete adapter rather
than holding two registries. The sentence stays, pointing at `binding.py` and
without the claim about one place, because `setup` still builds configs and
`cli.py` still imports both registries for it. Moving that too is the change
that would make the claim true.

`bind_run` takes the path rather than reading `DEFAULT_PATH` off its own module.
Read as a global it answers about whichever path the module named when it was
imported, which is a different file from the one a caller patched — which is how
the suite reached a real profile in a home directory the first time this moved.

A `Run(profile, runtime, agent)` type was considered for what `bind_run` answers
with and deferred. It would be three fields and no behaviour until there is a
lifecycle to hang on it, and that is #12's question rather than this one's.

The layer rule is stated by hand in three places — `COMMAND_LINE` in
`tests/test_architecture.py`, the `shared/` contract in `pyproject.toml`, and
the module map. A new module outside all three fails the suite, which is what
makes a fourth place to put code a decision rather than an accident. Proven by
taking `binding.py` back out of the layer and by pointing it at a concrete
adapter, and watching each fail.

## Letting go is a request, not a program on someone's PATH

The release went through `lms unload`. It fails two ways that the HTTP release
does not.

A missing `lms` is a run that dies at cleanup holding the model it loaded. It
ships with LM Studio, so it is usually there — but "usually" is the whole
problem: the failure lands after the agent has finished, on a machine that now
cannot use the memory until someone notices.

And the tool takes a model key while the memory it frees is per copy. LM Studio
does not replace a model when it is loaded again; it serves both. `lms unload`
given the key freed one of them, printed success and exited 0, leaving the rest
resident on a machine whose premise is one model at a time. Its exit code
cannot say otherwise: it exits 0 for a name it does not know.

The comment above the tool said the HTTP release was unreachable — that
`POST /api/v1/models/unload` wants an `instance_id` and the `/api/v0`
catalogue this adapter reads does not carry one, so the move waited on #18.
That was wrong. `/api/v0` lists each loaded copy as its own entry and the
entry's id *is* the `instance_id`: loading `qwen3-0.6b-mlx` three times gave
`qwen3-0.6b-mlx`, `:2` and `:3` from `/api/v0` and from `/api/v1`'s
`loaded_instances` alike, and the release accepted one taken straight from the
former. Nothing about this waits on #18.

So `let_go` reads what is held, releases every copy, and reads back. Three
things follow from the read-back rather than from the release's own answer,
which is why it stays:

- A model the runtime evicted for itself is memory that came back, not a
  failure, even though naming it is a 404.
- The named model is asked after whether the catalogue lists it or not,
  because a load that failed may have left weights the catalogue has not
  caught up with. What that costs where there is nothing is one 404.
- One copy that will not go is reported with what the runtime said about it,
  and does not stop the others being asked.

Proven live: two copies held, `let_go` called once, the catalogue empty after.
A fixture cannot make that claim — it can only repeat the `:2` convention it
was told.

## A caution rides on the launch, not on the agent port

Where offgrid will not size the agent's compaction, a person has to be told
before the run rather than mid-session. The words are the agent's own —
`/compact` is Claude Code's command, and the 100,000 it raises anything smaller
to is Claude Code's number — so the domain cannot write the sentence and the
command line cannot either.

A member on the agent port was the first shape and is rejected. The survey in
`docs/research/adapter-surfaces.md` has Codex documenting a
`model_context_window` with no clamp stated, and OpenCode's not established at
all — the doc that would say is recorded there as unread. That is enough: a
`read_compaction` every adapter had to answer would be one vendor's quirk asked
of all of them, and answered `None` forever by an adapter with no clamp to
speak of.

So `Launch` carries it. An agent with nothing to say builds a `Launch` without
it, which is the default. `plan` writes nothing and starts nothing, so `doctor`
could show the same sentence `run` does without paying for a load; today only
`run` prints it, and #93's story 16 is where that gets settled.

Not setting the variable is a claim about what the agent reads, so the launch
names it as dropped and it is taken back out of the environment the agent
inherits. Left merely unwritten, a `CLAUDE_CODE_AUTO_COMPACT_WINDOW` exported in
someone's shell would answer in offgrid's place — and it is the people who
followed a setup guide who are likeliest to have exported one, which is the
population this sentence exists for.

Where the runtime states no window at all, nothing is asked for either, and the
sentence says so rather than guessing. The old fallback asked for 32,768 there,
which Claude Code raised to 100,000 — a number picked by neither offgrid nor the
runtime, describing nothing. When the agent compacts is then Claude Code's own
business, which is worse than a window offgrid chose and better than one it
invented.

The number it turns on is not configurable and does not want to be. It is what
Claude Code does to what it is given, not a preference: asking for 32,768 gets
100,000 back, which is the truncation that reading the served window exists to
prevent. That is why nothing is asked for below it, rather than a smaller number
being asked for and hoped over.

## A window is written down beside the model, in a section of its own

#93 settled that a window would sit at the top level of the profile, beside
`model`, on that key's own precedent: it belongs to neither adapter, so it goes
where neither section can claim it. The layering argument holds and the shape
does not. `model` becomes a section carrying `identifier` and `context_window`,
and the two things that say what to run sit together in a file that is now
sectioned throughout. What the section belongs to is the same answer as before:
the agent sets the floor, the runtime honours the number, and the model states
the ceiling, so it is nobody's adapter's.

The section is a `ModelRequest`, which is the type `--model` and
`--context-window` already build and the runtime port already takes. Nothing
new is declared for the file, so a key the request refuses — an empty
identifier, a window of zero, a misspelling — is refused the same way from
either door. `settle_what_to_run` puts the two together key by key rather than
whole: a run naming a model and no window still wants the window somebody wrote
down, and reading the pair as one would drop it back to whatever the runtime
remembered, which is the number the profile was written to stop being the
answer.

`setup` writes the section even where it says nothing, so both keys are on disk
to be edited. The alternative was writing nothing until there was something to
write, which leaves the person who has just been told to load a model with no
sign of where to name it. What it costs is two null keys in a fresh profile.
A section that must be there was considered and set aside: `setup` runs before
anyone has chosen a model, so a required `identifier` means writing a profile
that the next `run` refuses. Whether a run should have to state its model at
all is #117, which supersedes rather than extends the decision that a run with
no model named uses whatever is resident.

`model: <a name>` is refused rather than migrated, the way the flat profile
already is, and the refusal prints the section to write with the name that was
already there — the fix is a copy over the line it replaces. Every profile in
existence is in that shape, including the one this was designed on, and a
silent rewrite of a hand-edited file is still worse than a clear refusal on a
project this size. What is echoed back is the name the file already carried, so
the fix is a copy over the line it replaces — and where the file carries
something that could not be a name, an example stands in, because a shape that
is refused when it is copied is not a fix. `model:` with nothing under it is
left alone: it says no model is named, which is a run against whatever is
resident.
