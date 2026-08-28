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
the adapter raises, which is every other one. What it costs is a sentence that
names no address where the other refusals do. What it buys is that a `Runtime`
is not made to expose an address for a sentence, which every adapter after this
one would have paid for.

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
`provider.<name>.options.baseURL` block rather than from a variable naming the
address, the way Claude Code reads `ANTHROPIC_BASE_URL`.

A file is not the only thing that block reaches opencode from:
`OPENCODE_CONFIG_CONTENT` carries the same JSON in the environment, and
measured on opencode 1.18.20 it outranks the file. That decides which half of
opencode's configuration states the address rather than whether the agent's
section carries it — the adapter is bound to what the profile settled either
way. Which half, and why, is under "What an adapter writes, and what one run
derives".

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
writing a module in no layer and by pointing one at a concrete adapter, and
watching each fail.

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
new is declared for the file, so the constraints are declared once and both
doors are held to them — an empty identifier, a window of zero, a window
written `yes`, a misspelling. Each door says so in its own voice: the file's
reader turns a validator's block of text into a sentence, typer refuses a
`--context-window` below one before the domain sees it, and
`read_what_was_typed` is where the command line's own empty name becomes a
sentence rather than a traceback. `settle_what_to_run` puts the two together key by key rather than
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
already is. Every profile that names a model is in that shape, including the
one this was designed on, and a silent rewrite of a hand-edited file is still worse than
a clear refusal on a project this size. What the refusal prints is the section
to write with the name the file already carried, so the fix is a copy over the
line it replaces — and where the file carries something that could not be a
name, an example stands in, because a shape that is refused when it is copied
is not a fix. `model:` with nothing under it is left alone: it says no model is
named, which is a run against whatever is resident.

`setup` does not rescue a profile in the old shape. It cannot read one, so it
sets the file aside as `.rejected`, says so, and writes a fresh profile from
the defaults — which loses a hand-edited address along with the model name.
That is the cost of refusing rather than migrating, and it is paid once, by
people who can read both files. Naming it here rather than building around it:
v0.1 is a handful of people, and the alternative shapes — `setup` refusing
too, or `setup` carrying the name across — either leave no command that
repairs the file or reintroduce the silent rewrite this decision turned down.

## The command line is a folder, one module per command

`cli.py` reached 278 lines, and the length hook is a ratchet: a file already
past 150 is left alone until an edit makes it longer. So the file could not
gain the line #118 asks for — a `doctor` report that says what the profile
asks for — without being split first, and nor could the next command's next
line. The split is what the hook was asking for rather than a detour around
it.

One module per command, named for the command it holds, with `reporting.py`
for what offgrid's own errors look like at the terminal — the one thing all
four commands share. `__init__.py` keeps the typer app, attaches the four, and
holds `main`, so the wiring is read in one place and what a command does is
read without it.

Each command is attached under a second name:
`from offgrid.cli.setup import setup as setup_command`. A command's module and
the function in it have the same name on purpose, and binding `setup` in the
package would rebind `offgrid.cli.setup` from the module to what is inside
it — which is where a test's patch target goes, and where a reader opens. The
alias sidesteps that: importing the submodule is what puts the module on the
package, and only the name this file binds is the alias.

`app.command()(setup.setup)` was the first shape and says the same thing
without the four extra names. It was turned down for how it reads at the
attachment, which is the one place somebody looks to see what the command line
answers to. Naming the modules for the action instead — `setting_up.py` — was
turned down for the opposite reason: it breaks the rule that a command's
module is named after the command, and a patch target stops reading like the
command it stands in for.

What it cost is that every name a command imported now lives in four places
instead of one: `detect` is in `setup.py` and `recommend.py`, `DEFAULT_PATH`
in all four. A test that patched `offgrid.cli.DEFAULT_PATH` reached one name
and now has to reach each. `tests/commands.py` is where that is done once,
and it lists the commands rather than finding them, so a fifth command added
without a line there fails a test instead of quietly reading the developer's
own machine.

## A file runs to 200 lines before anybody asks about it

The limit is a prompt to ask whether a file holds two ideas, and at 150 it was
answering that question itself: files that read as one thing were being split
because of a number, and a split made for length leaves two modules neither of
which says what it is for. 200 is where the question gets asked instead.

Nothing enforces it. A hook refused an edit that took a file past the number,
and what that bought was #169: two files shrunk to land on exactly 200, one of
them by deleting rationale that was still true. A guard that can be satisfied
by deleting the reasons is worse than the number it guards, so the number is
said to a person and they decide. Cohesion is what decides a split.

Whether the order of a run belongs in a domain module rather than in
`run.py` is still #12's question. This decision does not answer it; it makes
`run.py`'s real size readable, which is what #12 was waiting on.

## What the profile asks for is one line, labelled for its source

#118 left the wording open — "`asked` may want to name the source, since the
command line beats the file and `doctor` takes no `--model`". It is one more
line in the same column rather than a block of its own, because the point of
printing it is the comparison with the two lines above it, and a heading with
a blank line either side puts distance between the numbers a reader is holding
against each other.

The label is `profile`, which names where the statement came from, as
`runtime` and `agent` already do. That is what carries the one thing a reader
has to know: every other line is a reading of what is, and this one is an
instruction. `asked` was the issue's own sketch and needed a trailing clause
to say the same thing.

Each case says what a run would do rather than printing the keys: a model with
no window reads "at whatever it is served at", a window with no model reads
"whatever is held, at N", and a section saying neither reads "asks for
nothing, so a run takes whatever is held". A dash, or the `unstated` the
ceiling and window lines print, would each have been shorter and would each
have needed the reader to know that a missing key means inherit — and
`unstated` there means the runtime did not say, which is not what it would
mean here.

The sentence is built in `running/asking.py` rather than in the command,
beside `answering.py` and on the precedent of `recommendation.py`: what a
person reads is written in the domain and printed by the command line.

Annotating the readings instead — `window 212224 (profile asks 131072)` —
was turned down for one reason: a profile that asks for nothing then prints
nothing, and #118 asks for it to say so.

Whether `run` should name the model a window-without-a-model landed on, the
issue's other open question, needs no change. `hold_model` substitutes the
resident identifier before it returns, so the line `run` already prints is the
model it landed on.

## A command says lines something else built

`doctor` printed its report as eight `tell` calls and a conditional ninth.
`recommend` already did the other thing — `for line in summarize_findings(...)`
— and the two shapes were one command apart.

The report is a value now: `_describe` returns the lines in the order they are
read, and `doctor` says them. What that buys is not fewer calls. It is that
what the report says can be settled in one place and said in another, which is
what #124 needs — a runtime holding nothing has to leave the model lines out
or mark them unknown, and that is a list to build against rather than a run of
statements to thread a condition through.

Reading is behind `@reporting()` where the reading is more than one statement
or answers with more than one thing — `setup` and `doctor`. Nothing in
`reporting.py` changed to allow it: calling a `@contextmanager` function gives
an object that is already a `ContextDecorator`. What it costs is that the
scope stops being visible at the call site, and a line that looks total can
end the process; what it buys is a command body that reads as what the command
does.

A single call keeps its `with`. `recommend` was written both ways and the
extraction lost: a nine-line helper whose whole body was `return
get_reading(LEADERBOARDS, _cache())`, under a name that says less than the
call it hid, and a docstring that restated the callee's and got it wrong on
the first try. `reading = get_reading(LEADERBOARDS, _cache())` inside a `with`
says where the table comes from; `reading = _read_a_published_list()` puts
that one indirection away for nothing.

`run` keeps its `with` for a second reason on top of that one. Its later block
wraps a single statement *inside* the `try` whose `finally` owes `let_go`, and
a decorator can only mean a whole function, so extracting the first block
would leave one command spelling it both ways — worse than one command
spelling it differently. The alternative, moving the release out of the
`finally` to make the shape uniform, breaks what has to survive Ctrl-C (#11).

`doctor`'s reads come back as a four-value tuple, which is a clump wanting a
type. It is left as a tuple until #124, which needs a shape that can say "the
runtime holds nothing" — that is the change that tells us what the type should
hold, and "A report reports" below is what it told us.

## A layer is a folder, and binding is in one

`binding.py` sat at the root of the package while every layer around it was a
folder. The tree is what says which layer a module is in, and it could not say
this one — so the answer was written by hand in three places instead: the
`shared/` contract in `pyproject.toml`, `COMMAND_LINE` in
`tests/test_architecture.py`, and the module map. Under `cli/` the name already
in the first two covers it. The map keeps its line, because it names every
module there is by hand and a layer's name covers nothing there; what changed
is that the line is indented under the folder rather than standing alone at the
root.

The decision above — that binding a run is its own module and the command line
is not it — is not what this reverses. What that one turned down was
`read_profile` living in `cli.py`, where the module a function happened to sit
in became the interface every test reached through. A file of its own inside
the folder is not that, and `reporting.py` is already there without being a
command. What `cli/` holds is the layer; what it holds a module per is the
command.

The cost is that `offgrid.cli.binding` runs `cli/__init__.py` on the way in,
which builds the typer app and imports all four commands. `test_profile.py`,
`test_profile_model.py` and `test_live.py` read a profile and now pay for the
command line to be built to do it. Measured at about 12ms on top of the 100ms
binding's own imports already cost, because typer arrives with `shared/say.py`
and both registries are on that path anyway. Weighed against a layer the tree
states rather than two files, and taken.

## A report reports, and a finding is a line in it

`doctor` read the resident model before it printed anything, so a runtime
holding nothing replaced the whole report with one sentence — including the
`model:` line the profile had just gained, which is the line that case is worth
most in. A profile naming a model to load is a statement about a model the
runtime is *not* holding.

Worse than quiet: the sentence was false about such a profile. `hold_model`
reaches for the resident model only where nothing named one, so `offgrid run`
would have loaded what `offgrid doctor` sent someone to load by hand. The
refusal was a finding about the runtime rather than a fault in reaching it, and
every other line beside it was true.

So the model's lines stay in the column — `nothing held`, and `unknown` for the
two numbers that were about it. Marked rather than left out, because a number
about a model that is not held is unknown, where `unstated` is what a held model
states when the runtime says no number for it: two statements that one blank
would collapse.

The exit code is the one it already was. `1` is what every `OffgridError`
exits with, so it says a report was not a clean run and nothing finer than
that — a script cannot tell holding nothing from a profile with a typo in it.
Keeping it is what #124 asked for; what a script would need to tell the two
apart is a code of its own, and no evidence yet says anyone wants one.

What to do about it is said only where nothing names a model at all, which is
the pairing a run has no name to reach for. Where the profile names one, the
`profile` line already says what would be loaded — and whether the runtime has
that model to load is the runtime's own answer, which `doctor` does not ask for
and a run gets by name.

The shape #124 needed is `Model | None`, which the tuple could have carried
too. What the `Checkup` the clump became is worth is the reading beside it: a
named field to branch on, room for a sixth reading, and — since it holds what
each of them answered rather than the things that answered — no agent port,
and so no `configure()`, inside the value a report that writes nothing is
built from.

Reading one takes `find_resident_model`, which answers with what is held or
with nothing. `get_resident_model` is that reading plus the refusal, for the
caller that cannot go on without one.

## A window a runtime will not grant is written down, not asked for twice

LM Studio serves some models at a window of its own choosing whatever a load
asks for. `offgrid run` asked for the profile's window, read back another, and
`ensure_only` compared the two and reloaded to close a gap that could not
close. The reload is what costs: it empties the runtime's prompt-prefix cache,
so the first turn of every session paid a full cold prefill. Measured on this
machine against `qwen/qwen3.6-35b-a3b` — a turn reading 19,968 of 19,991
tokens from cache took 2.02s, and the same turn after a reload read none and
took 60.4s. Every run, forever, because the mismatch was permanent.

Upstream calls it a bug —
[lmstudio-ai/lmstudio-bug-tracker#2250](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2250),
"MLX models ignore every user-configured context length" — and says the
GGUF path honours the value. Which models it strikes is not settled: on this
machine two discard the window and two honour it, and the two that discard it
are both vision-capable *and* both large, so nothing here separates the two
explanations. #136 holds the evidence.

So offgrid does not predict it. Encoding "vision-capable MLX models discard
the window" into the domain would be wrong today, since it is unproven, and
wrong the day upstream fixes it. What offgrid does instead is remember what a
runtime actually did with a window it was actually given, and stop giving it
that window again.

**The fact is kept, not the verdict.** The record says what was asked, what
came back, and when. It does not say "this runtime is broken" or "never ask
again" — whoever reads it decides, and a policy that changes does not have to
migrate a file written under the old one.

**Only the same window is left unasked.** A refusal is about the number it was
given. Reading it as a fact about the model would drop a `--context-window`
somebody typed on the strength of an answer about a different one, and then
tell them the runtime had refused a number it was never shown. A window that
differs is a question the runtime has not been put, so it is put — which is
also how a runtime that has started granting windows gets noticed.

**Every window a runtime discarded is kept, not the last one it discarded.**
Asking for the same window again restates its answer; asking for a different
one adds an answer beside it. Keeping one record per model instead would mean
a run going back to an earlier window finds nothing about it, puts the runtime
a question it has already answered, and pays the release and load that
answering it costs — which is the reload the record exists to save. Two
windows alternating would defeat the file entirely, and a profile window with
an occasional `--context-window` beside it is exactly that shape. So the file
grows by the windows that were asked for rather than by the runs that asked.

**The refusals still come first.** A window below the agent's floor or above
the model's ceiling is refused before the record is consulted, so a number
that could never work is said to be one whether or not offgrid meant to send
it. The cost is a catalogue read on a run that was going to drop the window
anyway; the alternative is silence about a typo.

**Nothing expires.** No TTL, no re-check on a schedule. The runtime exposes no
version offgrid can key on over HTTP, and a timer would reintroduce the
sixty-second turn on a schedule with nothing to show for it. Deleting the file
is how a person says to ask again, and `offgrid doctor` names the file, since
that is the command someone runs when something is not what they asked for.

**It is keyed on the runtime, its address, the model and the window.** Two
models on one server disagree about this — measured — one model may be
reached at two addresses, and an address names one server at a point in time
rather than for all time: a runtime that stops listening on `127.0.0.1:1234`
and another that starts there must not be answered with each other's records.
No one of the four is the thing the behaviour belongs to.

**Two sentences, because offgrid knows two different things.** Where it put
the window to the runtime and read the answer back, it says the runtime did
not grant it: a claim about the runtime, with the evidence in hand. Where it
asked for nothing because that same window was already on record, it says so,
dates the refusal it is repeating, and names what the runtime is serving now: a
claim about the record and about what was read back. The first would be an
unfounded attribution in the second case — offgrid made no request that run,
so nothing of the runtime's was observed. Saying the model was "already held"
would be a third claim, and a worse one: it may have been loaded in the same
breath, and offgrid never checked.

**Neither sentence says "bug".** Whose fault it is, is exactly what #136 does
not establish.

### What it cost in shape

`hold_model` is handed the question rather than the address to answer it from
— `was_window_refused_func: Callable[[str, int], bool]`, closed over records
the command line read once. Handing it a host would have given it two sources
of truth for one connection, with nothing able to detect them disagreeing, and
would have had the domain reaching for a file behind its caller's back. It is
the same rule `reading.py` follows: handed the lists rather than reaching for
them, the way `answering.py` is handed a `Runtime`.

It takes the model as an argument rather than closing over one because at the
point the command line reads the file, there may be no model named: a run that
gives neither `--model` nor a profile model is answered with the resident one,
and `hold_model` is what resolves that. `doctor` has already read the resident
model, so it is the only caller that can ask the narrower question — which is
why the store hands back the records it read and leaves indexing them to
whoever asked.

The records are read once per command and shared. The question "was this
window refused" is asked twice in a run — once to decide what to request, once
to decide what to say — and answering it from two separate file reads is how
the two answers come apart.

`discarded_windows.py` is the store and `discarding.py` is the deciding, which
is the split `sizing/cache.py` and `sizing/reading.py` already make. The store
holds no opinions; the deciding holds no file.

The file is read the way the profile is read: a pydantic model that refuses a
key it does not name, and a runtime read as a `RuntimeName` rather than a
string, so a name offgrid has no adapter for is a mistake in the file rather
than a record about nothing. A record offgrid cannot make sense of is said out
loud rather than skipped, because a run that silently reads no memory goes back
to paying the reload. A file that is not there stays silent — that is every
machine before the first window is discarded.

One thing the suite cannot hold yet: only `lmstudio` has an adapter, so
deleting the runtime half of the key leaves every test green. What is covered
is the record a file holds and the names it refuses. The guard becomes
testable with the second adapter.

## A runtime serves a set of dialects, not one

The runtime port carried a single `dialect`, and the LM Studio adapter stated
`anthropic`. So `require_compatible` refused an agent speaking `openai` against
a server that serves it — the refusal was offgrid's model of runtimes rather
than anything the runtime does, and the second agent could not be run at all
until the model was fixed.

The survey that contradicted it was already in the repo.
`docs/research/adapter-surfaces.md` records all four candidate runtimes
exposing both shapes, and this decisions file has said since "A port states
what is wanted" that the pairing check no longer discriminates between
runtimes. The port outlived the finding.

So a runtime answers with a `frozenset[Dialect]` and the check is a membership
test. An agent speaking any one of the set pairs with the runtime; an agent
speaking something outside it is still refused before a load, which is the case
the check exists for — Codex CLI accepts only the Responses API, and there is
nothing among these runtimes that serves it.

**The set is a constant, settled without reaching the server.** It sits in
`runtimes/lmstudio/serving.py` beside the capabilities, because what LM Studio
exposes is a fact about the application rather than about one connection to it.
That is what lets an impossible pair be refused before a run pays for a load,
which is the whole value of refusing early.

**What it does not claim is that either shape is served completely.** Exposing
an endpoint and serving a dialect are different statements, and LM Studio
answers `count_tokens` with a `200` while logging that the endpoint does not
exist. What a runtime owes to count as serving a dialect fully stays open as
issue #43, and the constant carries that caveat where a reader will meet it.

**An empty set is a fault in the adapter, and the refusal says so.** Offering a
translating proxy to somebody whose runtime serves nothing sends them to build
a translator with one end unattached, so that message names the adapter
instead. The conformance suite is what holds every adapter to a non-empty set;
nothing in the type says it.

**The dialects are named in sorted order.** A dialect hashes by its name and
string hashes are salted per process, so a message built from the set's own
order names them differently between two runs of the same refusal. Sorting is
one line and it is what makes the sentence quotable in a bug report.

## What an adapter writes, and what one run derives

`configure` writes where there is no edit to lose and never touches one that is
there, because it cannot tell offgrid's own earlier write from a person's
deliberate edit. What counts as an edit is settled further down, under "A
configuration is decided by what it holds, not by whether it is there". Against
OpenCode it decides a second thing: anything
derived from the profile, written into that file once, is silently wrong the
moment the profile changes. A moved address, a different model, a different
window — the file keeps saying the old one, and an address OpenCode cannot
reach **hangs** rather than erroring, measured on 1.18.20 at a dead port as
much as at a wrong one. That is the failure nobody gets a message about.

So the split is not between a file and an environment. It is between what
offgrid never revises and what one run settles.

**The durable half** is the provider entry's shape: the published `$schema`, so
the file a person is meant to edit gets completion and validation; the npm
package that speaks the OpenAI-compatible protocol; the label OpenCode
displays; and `share: disabled`, which is the setting in that file deciding
whether a transcript leaves this machine. Sharing goes here rather than in the
derived half because it is a standing choice about this machine — somebody who
wants sharing back keeps the edit.

**The derived half** is where the runtime listens, which model answers, and the
window and output cap it answers at. It travels as inline configuration in
`OPENCODE_CONFIG_CONTENT`, rebuilt every run, so none of it can go stale and
`plan` still writes nothing — the address is then something a person can be
shown before anything starts, which a file's contents are not.

**The ordering the split rests on was measured**, on opencode 1.18.20, with all
three configurations deliberately set to conflicting values:

    inline  >  the file offgrid writes  >  a person's own configuration

and measured both ways round, because `configure` never overwrites: an address
hand-edited into offgrid's file has to lose to the derived one. The three deep
merge rather than replace, so a person's own provider entry, key and timeouts
come through a run untouched, and only a key offgrid names is overridden.

**The provider is called `offgrid` rather than the runtime's name.** OpenCode
takes any string, so nothing requires it to be one — and making it one would
put a fact about runtimes inside an agent adapter, and would deep-merge with a
provider entry a person wrote for that runtime themselves. A name of offgrid's
own collides with nothing they wrote.

**The model is enumerated rather than named.** Measured on 1.18.20, a provider
entry carrying the package and the address but no model list resolves no model
at all, so pointing at the provider is not enough to reach one.

Two smaller things fall out of the same axis. The window written is what the
runtime settled on rather than the model's ceiling, because telling OpenCode
the larger of the two asks it to compact after the runtime has already
truncated the prefix. And where the runtime states no window, the entry carries
no `limit` at all rather than one naming an output cap alone: the published
schema requires `context` and `output` together and refuses the half, so the
cap goes with the window. That is a real loss, and issue #154 is what a person
is owed about it.

## A project configuration is switched off, and a person is told before the run

A configuration in the directory a run started from beats the file offgrid
writes. It does not beat what the run carries inline — measured on opencode
1.18.20 with a project file pointing the provider at a dead port, which
answered through the derived address rather than stalling. So the address is
safe either way.

What it is not safe from is everything else such a file states: providers,
agents, permissions and the instructions a project keeps in `AGENTS.md`,
`CLAUDE.md` or `CONTEXT.md`. offgrid never writes any of those, so it cannot
outrank them, and a run that quietly picks up a project's own agents and
permissions is not the run offgrid described.

`OPENCODE_DISABLE_PROJECT_CONFIG=1` covers the class rather than the one key,
and that is why it is set even though the address needs no defending. What
OpenCode reads as true was measured too: it lowercases the value and takes `1`
or `true`, so `0`, `yes` and an empty string alike leave project configuration
read — the constant is named for what it switches off rather than for the
string it happens to be.

**Because that takes something away from somebody who put it there
deliberately, the launch carries a caution.** That slot already exists, for the
compaction window Claude Code will not honour, and it exists for this reason:
what there is to say is one agent's own, so the domain cannot word it and a
member every adapter had to answer would be one vendor's quirk asked of all of
them.

Where it lands is one line before the agent starts, and not before the model is
held: a caution rides on a `Launch`, and a `Launch` is what `plan` builds out of
the model a run has already settled. So a person reads it after paying for a
load rather than instead of paying for one, which is later than #148 asked for.
Nothing about this sentence depends on the model, so what would move it earlier
is a way for a caution to be read before `plan` — which is the same question
#93's story 16 asks about showing one in `doctor`, and is not settled here.

**The caution is a standing statement, not a finding.** Saying it only where
such a file exists would mean reimplementing OpenCode's own upward directory
walk — its stopping condition and both file spellings — to word one sentence,
and a walk that drifted from theirs would say the wrong thing confidently. For
the same reason the sentence names what a person is likeliest to have rather
than claiming a complete list, and says what to do instead: start OpenCode
yourself to use what a project states.

What was turned down is doing nothing at all, on the strength of inline
configuration outranking a project file. That reading is correct, and it covers
one key out of a class.

## A configuration is decided by what it holds, not by whether it is there

Both agent adapters wrote what was missing by asking whether the file existed.
A file that was there and said nothing — emptied, cut off part way, edited down
— therefore got nothing written and no error. For OpenCode that costs the
package, and measured on 1.18.20 a provider entry without it resolves no model:
the run loops and then fails with "Model unloaded." Sharing disabled is in the
same file, and that is the promise about transcripts made above.

**What decides is now whether the file holds an edit somebody made.** No file
and an empty file answer alike, because whatever emptied it left nothing
anybody chose, so offgrid writes into it. A file that holds something offgrid
cannot read at all is refused, naming itself: bytes that are not text, and
settings that are not JSON. `domain/running/keeping.py` answers that once for
every adapter rather than each adapter answering it, because deciding it per
adapter is how one of them came to decide it by existence alone.

**What was turned down is merging the missing keys back in.** It is the reading
the OpenCode spec in #147 argued for — "writes the provider entry, its package,
its label and sharing disabled" is key-level language — and it contradicts a
promise the port already makes. `configure` may not write over an edit that
leaves a hosted tool reachable, because `read_hosted_tools` reports that edit
with a remedy and a run refuses on it. The stand-in's own example is a settings
file holding `{"theme": "mine"}`: merging would put `permissions.deny` back
into it, so the guard could never report `PERMITTED` on the ordinary path
again. A refusal a person can act on would have become a silent rewrite of
their file, which is the failure the seam was split to prevent.

So two things stay unfixed on purpose, and both are silent. A file edited down
to keys offgrid never wrote keeps them and gets nothing added; and a key
offgrid starts writing in a later version reaches no file that is already
there. The second is the upgrade path #155 asked about, and it is out of scope
rather than handled — what a person gets instead is a guard that reads the file
and refuses the run, which OpenCode does not yet have for sharing.

**Whether there is an edit is asked of the file's text, not of what the text
parses to.** `null` is a document somebody could have left and is also how
"nothing" is spelled, so deciding off the parsed value would write over that
one file and no other.

A symbolic link whose target is gone is refused rather than followed. It is
absent by every reading that follows it — `Path.exists()` included, which
swallows the error and answers False — so the check for absence said write, and
the write followed the link and created the target outside the directory
offgrid owns, with nothing said about it. A link to a file that is there is
still followed, because pointing a configuration somewhere else is a thing
people do deliberately.

## A run is asked what could leave this machine, not what tools are hosted

The slot that read hosted tools now reads everything a run could send off this
machine, and answers one reading per subject rather than one status. `Subject`
names them — hosted tools, transcript sharing — and `require_nothing_leaves`
refuses on the first that is not settled.

**What made it necessary is that OpenCode's `share` was written once and never
read.** `configure` leaves an edited file exactly as it found it, correctly,
and the adapter answered about hosted tools from a constant, correctly. So the
one file deciding whether a transcript leaves this machine had nothing reading
it: a person who turned sharing back on, or who edited the file down to keys
offgrid never wrote, got a clean `doctor` and a run that went ahead. That is
the guard the entry above promised and did not have.

**One slot rather than two.** A second port member would duplicate the enum,
the guard and the conformance shape for a question with the same four answers
and the same decision behind it. What a second member would have bought is
telling the two apart, and a reading carrying its own subject buys that instead
— `run` refuses naming which one, and `doctor` prints a line each.

**One reading per subject rather than one status.** Folding them would make a
refusal unable to say which of the two caused it, and they are fixed in
different places by different edits: a key in a JSON file, an argument on a
command line. `tests/test_agent_leaving.py` asks every adapter for every
subject, so a subject added later goes red on every adapter rather than on
none — which is the only thing standing between a new subject and an adapter
that silently never answers about it.

**What `share` unset means is unknown, and that is the measurement.** The
published schema states an enum of `manual`, `auto` and `disabled` and no
default. Measured on 2026-08-25 against opencode 1.18.23, and the isolation is
the measurement — pointing `OPENCODE_CONFIG` at an empty file is not enough,
because a person's own `~/.config/opencode/opencode.json` still deep-merges
under it and supplies whatever `share` they set. Read this way instead, from a
directory with no configuration in it:

```
printf '{}' > /tmp/empty.json
env HOME=/tmp/none XDG_CONFIG_HOME=/tmp/none/.config \
    OPENCODE_CONFIG=/tmp/empty.json OPENCODE_DISABLE_PROJECT_CONFIG=1 \
    opencode debug config
```

What comes back holds `$schema`, `agent`, `mode`, `plugin`, `command` and
`username`, and no `share` at all: it is absent from what OpenCode resolves
rather than filled in. Run without `XDG_CONFIG_HOME` the same command answers
`"share": "disabled"`, which is the reader's own setting and not a default —
that reading is how this claim gets doubted, so the isolation is written down
rather than assumed. `opencode debug config` also rewrites the file
`OPENCODE_CONFIG` points at, so it is pointed at a throwaway. So offgrid cannot say a
transcript stays here, and an edited file that states no `share` answers
`UNWRITTEN` and stops the run. Its remedy is the edit rather than "run again",
because `configure` will not write into a file holding an edit — which is why
the remedy travels on the reading and is not read off the status.

**Claude Code answers about sharing too, and not with `NONE_OFFERED`.**
Measured against claude 2.1.245 by reading `--help`: `--cloud` opens a session
on Anthropic's servers and `--environment` opens one on a named self-hosted
pool, so a run carrying either is not a local run whatever the profile names.
There is no setting for it, so the whole of the reading is the command line.
`--teleport`, `--remote-control` and `--from-pr` each touch a session somewhere
else and none was measured; claiming a complete list off `--help` would be the
invented fact this file exists to keep out, so they are issue #167 instead.

**`doctor` prints a line per reading, and `DENIED` alone prints no detail.**
That is the one answer with nothing behind it to check and nothing to act on.
`NONE_OFFERED` still prints its evidence, because a claim that an agent has no
such thing is worth exactly what the dated measurement beside it is, and the
report is where a person reads that.

## The command line is read before the file, for both agents

Review found the same silent failure #162 was filed about, one layer over.
`opencode run --help` at 1.18.23 offers `--share`, "share the session".
`offgrid run` hands the whole command line through, and the OpenCode reading
was taking only the file — so `offgrid run -- run "..." --share` answered
`transcript sharing: denied` off a file saying `disabled` and started the run.
A file was answering a question nobody had asked.

**So a reading takes the passthrough as well as the settings, and reads the
argument first.** That is the shape the hosted-tool reading already had, where
`--setting-sources` decides whether the file binds at all; sharing is the same
sentence with a different flag. `Status.PERMITTED` had said so all along —
"an argument may ask for it directly" — and one adapter did not.

Whether `--share` beats `"share": "disabled"` in the file was deliberately not
measured, because measuring it means publishing a real session. offgrid does
not need to know: it cannot promise a transcript stays here while an argument
asks for one, so the run stops either way and names the argument.

## The guard counts the readings it was given

`require_nothing_leaves` iterated and raised on the first unsettled reading, so
an adapter answering `()` — or about one subject and not the other — was
refused nothing and started. The module said this belonged in the conformance
suite because only a suite asking every adapter can see it. That was wrong
about the function: `Subject` is in scope, the whole tuple is in hand, and the
suite's list of adapters is hand-maintained, so a third adapter added to the
registry and not to that list would have been type-correct and unasked.

It now refuses a tuple that does not answer every subject exactly once, as a
`ValueError` rather than the error a person reads: an adapter is wrong, not a
machine. It refuses in `Subject` order rather than in the adapter's, so a
person gets the same one thing to fix each run until they have.

**A `Reading` is checked where it is built.** An unsettled reading with no
remedy refused a run while saying nothing to do, and `remedy` defaulting to
empty made that the easy mistake. Both invariants — a detail always, a remedy
wherever the reading stops a run — are now the constructor's, so an actionless
refusal cannot be built rather than being caught by whichever conformance test
happens to exercise that path.

## An address is what a client does not ask for itself

Issue #156 read the `/v1` in the OpenCode adapter's `baseURL` as a fact about
where a runtime serves its OpenAI API, asserted two layers from where a runtime
is described, and asked whether it belonged beside `Dialect` or on the runtime
port instead.

Measured against a server logging the path it was asked for: opencode 1.18.23
through `@ai-sdk/openai-compatible` asks for `/chat/completions`, and claude
2.1.246 asks for `/v1/messages`. Both endpoints sit under `/v1` on LM Studio,
which `tests/test_live_dialects.py` already proves by refusal. The two adapters
carry different addresses because their clients ask for different amounts of
the path, not because the runtimes differ.

**So the address stays in the agent adapter, stamped with what was measured.**
Moving a prefix to the runtime port cannot work: a runtime stating `/v1` for the
Anthropic dialect — where it truthfully serves it — would hand Claude Code
`http://host/v1` and make it ask for `/v1/v1/messages`. A runtime-side answer
would have to state whole endpoints and have each agent adapter subtract its own
client's suffix, which is more machinery for a fact one adapter already knows
about itself.

What the second runtime falsifies is the other half of the sentence: a runtime
serving the OpenAI dialect anywhere but `/v1` breaks this address, and the
comment names that runtime so the claim can be checked rather than assumed.

## A conversation started here is resumed here

`claude --resume <id>` typed in an ordinary terminal answers "No conversation
found with session ID", for a session offgrid started minutes earlier. The same
argument through `offgrid run -- --resume <id>` opens it. The transcript is
intact and where offgrid put it: measured against claude 2.1.245,
`CLAUDE_CONFIG_DIR` decides where conversations are written as well as where
settings are read, so pointing it at `~/.offgrid/claude-code/` moved every
conversation there with it.

**That stays, because the alternative is a session answering from somewhere it
was not written for.** A conversation started here answers from a model held on
this machine, with hosted tools denied and a window of tens of thousands of
tokens rather than hundreds. Left in the directory the agent uses by default,
it appears in the picker of a run against a vendor's model, where resuming it
silently changes which model answers and what the session costs. The other
direction is worse: a long conversation from such a run, resumed against a
model held here, has its prefix truncated to fit.

**So an offgrid run is its own installation, and that is the whole state and
not the conversations alone.** Plugins, hooks, a person's own instructions and
the agent's onboarding are all in it, and none of them reach a run. One
directory per agent under `~/.offgrid/` is what makes that true, and splitting
it is not on offer: claude 2.1.245 has no argument or variable that separates
where conversations are written from where settings are read.

**It is what offgrid does, not a promise about what cannot happen.** Offgrid
puts no conversation of its own where a run against a vendor's model would find
it. It cannot stop one being copied there, and nothing in a transcript says
which kind of model wrote it, so a guarantee is not offgrid's to make.

**OpenCode keeps to it through `XDG_DATA_HOME`, and its conversations were the
evidence it did not.** The database under a person's own data directory holds
132 assistant messages naming provider `offgrid` — a provider that exists only
in what a run derives inline, so those conversations name a provider nothing
outside a run has. What happens on resuming one outside a run was not measured,
because measuring it means generating against whatever it resolves to. Those
stay where they are; what a run writes from here does not join them.

**Moving them is two variables, and one variable read as all of it.** Measured on
opencode 1.18.23 and through a real run, `XDG_DATA_HOME` moves the database,
`repos/`, `snapshot/` and the log. That it also moves the `credential` table is
a reason rather than a cost — a run that cannot reach a person's saved keys
cannot spend them, which is the same sentence the rest of this file makes about
hosted tools and sharing. What the same measurement found is that
`prompt-history.jsonl`, which records what a person typed, is under
`XDG_STATE_HOME` instead, so a launch carries that variable too, at `state/`
beside the store. The variable being nobody's in particular is what made one of
them read as enough.

**What a person typed only lands where the interactive interface writes it.** A
one-shot `offgrid run -- run "..."` leaves `locks/` under the state directory
and nothing else, so the suite as it stood would have called the store the whole
of it either way. Measured on opencode 1.18.23 by typing into the interface and
then through a real run: `prompt-history.jsonl` and the `model.json` recording
what was last answered through both land under the moved directory, and a
person's own history is untouched. A directory a run writes nothing into on the
path the tests take is a directory that has to be measured the way a person uses
it.

**Where a conversation is kept is its own member on the agent port, beside what
could leave this machine.** It reads as though it belongs among the subjects:
one line in `doctor`, one module per adapter, a conformance suite that makes
every adapter answer. But `Status` does not fit it. A directory is not
`DENIED`, `PERMITTED` or `UNWRITTEN`, and `NONE_OFFERED` would say the agent
keeps no conversations at all. Every subject there is about a run sending
something out; this is about where finished files sit, which is a hazard even
though nothing left the machine. A fifth status used by one subject would say
the two are the same question, and they are not.

**`doctor` says it on every run rather than where an installation is kept
apart.** After OpenCode moves there is no other case, and a branch with one arm
would claim a second kind of agent that does not exist.

## The picker is built before the second runtime, and pays for it

Two orders were available. The second runtime first, so that the picker's
model row and its dialect-refusal pane are each drawn from two implementations
rather than one; or the picker first, accepting that both are generalisations
from LM Studio alone. The second was chosen on timing: the picker is what
someone arriving from the README meets, and the second runtime is what a person
who is already running gains.

**The cost is named rather than discovered.** The two surfaces expected to move
when the second runtime lands are the model row's columns — identifier, held,
size on disk, ceiling, fits — and the dialect-refusal pane, which names every
dialect a runtime serves. Both are shaped by what one adapter happens to be
able to answer. The runtime conformance suites are what will show the
difference, because they are what asks every adapter the same question.

Nothing else in the picker is expected to move. The keys, the widget, the
report pane's arithmetic and the write-back are all about offgrid rather than
about a runtime.

## The picker exits before the agent starts

It is a launcher, not a wrapper. No pty, no drawing around a foreign terminal
application, no owning the screen while the agent has it. `run` carries out the
same sequence in plain text whether it was reached from the picker or from a
command line — the same steps, the same wording, the same exit codes — and the
picker never holds or lets go of a model itself. Arming records a wish.

**This is the same sentence as "a model is let go when the agent exits".** offgrid
waits for the agent rather than becoming it, so that a model is let go when the
agent exits; a surface that stayed on screen for the length of a session would
be a second thing holding the terminal for exactly as long. Keeping offgrid's
screen time to the bookends around a run is also what keeps the run sequence in
one place: duplicating it inside a widget is how two surfaces come to word the
same fact differently.

## Textual is chosen for its test driver, not for its widgets

Textual, over three alternatives. Rich alone is a renderer with no input loop
or focus model. prompt_toolkit is lower level and its test story is thinner.
Sequential prompt libraries have no persistent screen, so no report that
recomputes as a highlight moves.

**The deciding factor is `Pilot`.** This project tests what a person sees, at
seams that are named in `CLAUDE.md` before anything is built. A toolkit whose
surfaces can only be checked by a human looking at them would have made the
picker the one place that rule does not hold, on the day it was written.
Textual is also pure Python with no build step, which matters for a project
that is cloned rather than installed.

Frame snapshots are rejected for the same reason they are elsewhere: they break
on every cosmetic change and pass on wrong content, which is the inverse of
asserting on the message a person reads.

## Writing the profile back keeps the file a person's

The README advertises `profile.yaml` as hand-editable, and the adapters' own
config files are written once and then left alone. A picker that saves by
dumping the parsed document back would take a person's comments and key order
with it the first time they pressed the key that writes.

**So the write-back round-trips, and that is a new dependency.** The current
library dumps only; preserving comments, key order and formatting means one
that parses into a document it can write back. The cost is one more thing to
install for a surface that is not the only way to edit the file. It is paid
because the alternative is a save that quietly destroys the thing the README
told a person they could do.

**An unasked-for window stays unwritten.** `model.context_window` is saved only
where a window was explicitly chosen. An absent window means whatever the
runtime remembers, and materialising it into a number is a behaviour change
wearing a save's clothes.

## An agent states its command, and one function does the lookup

The `Agent` port gains a stated fact beside `dialect` and `context_floor`: the
command a launch would run. Presence is then one domain function doing a `PATH`
lookup, and the picker and `doctor` both call it.

**It is not an `is_present()` per adapter.** The behaviour is identical for
every agent, and a port member that every implementation answers the same way
is an invitation to drift — one adapter resolving symlinks, another checking a
directory, and two surfaces disagreeing about one machine. It cannot be derived
from the adapter's name either: `claude-code` runs `claude`. Nor from a
`Launch`, since building one needs a `Model`, and the whole point is to answer
before a model has been loaded.

**`doctor` gains the line too.** Without it the picker would know something
about the machine that the report does not, which is the failure the shared
lookup exists to prevent. Presence is tested against a `PATH` the test
controls, never against whatever is installed where the suite runs.

## What the picker assembles is a profile, because a plan is something else

Runtime, agent and model are exactly what the profile holds, so the picker is a
profile editor whose subject happens to be in memory rather than on disk.
`enter` runs with it and makes it the remembered one; `s` runs with it once.

**It is deliberately not called a plan.** `Agent.plan(model) -> Launch` already
owns that word: a plan there is what one agent adapter builds for one model,
after everything has been settled. A second meaning — everything a person
assembled before anything was settled — is precisely the collision the glossary
exists to prevent. `CONTEXT.md`'s `profile` entry widens by a clause instead,
and this feature introduces no new vocabulary at all.

## `enter` writes, because that is where the reflex was learnt

Three keys: `enter` runs and saves, `s` runs for this run only, `q` leaves
having changed nothing. This is the polarity Claude Code's model picker
documents — "`Enter`: switch model and save as your default", "`s`: switch
model for this session only" — and most people meeting offgrid will have learnt
it there. Inverting it would turn a reflex into a trap.

**The safer polarity was passed over knowingly.** The reverse — `enter` for
once, a second key to save — cannot destroy anything by muscle memory, and here
the write is wider than Claude Code's: offgrid's profile carries runtime, agent
and model where `/model` writes one field, so trying an agent once rewrites
three keys unless the other binding is remembered. The mitigation is on screen
rather than in the keymap. The footer says which key writes, the footer says
when what is assembled differs from what the file holds, and a save says what
it wrote rather than only naming the model.

**The convention is evidence, not a fixed point.** Claude Code moved this
binding once already: in v2.1.144 through v2.1.152 `d` saved a default and
`Enter` applied to the session only, and by v2.1.153 it was the present
arrangement — nine patch versions. Whoever revisits this should check what it
does now rather than trusting the sentence above.

## A row that cannot be armed is the widget's guarantee, not a hand-written one

Every list is an `OptionList`. Read at Textual 8.2.8, `DataTable` has no
per-row disabled concept at all — `disabled` there is the widget-level one
inherited from `Widget` — while `OptionList` takes `Option(..., disabled=...)`,
dims the row, and refuses to rest a highlight on it or to emit a selection from
it.

**The constraint decides the widget, and it is not about looks.** Absent
things — an agent that is not installed, a model that does not fit — must be
visible and unreachable. With `OptionList` that is the cursor's own behaviour;
with `DataTable` it would be a refusal written by hand on select, in a surface
built specifically so that nobody discovers an absence at exit `127`. A guard
someone can forget to write is not the same guarantee as one that cannot be
reached around.

The cost is real and accepted: columns are padded text rather than real ones,
so alignment is ours to keep, and there is no sorting for free. The only
ordering needed is held models first, which is ours anyway because it is about
what a load costs rather than about the strings in a column.

## The fit column is table stakes, and the served window is the part nobody has

`docs/research/picker-idiom.md` was written to survey the idiom and falsified a
third of what this feature was assumed to be for. Recorded here so that the
assumption is not rebuilt from memory, and so the README does not claim it.

**Showing whether a model fits this machine before committing is not novel.**
Jan has carried a per-row fit pill since v0.8.0, computed from weights plus a
cache estimate against usable memory, with a branch written specifically for
Apple Silicon. Its estimator scales the cache with a window, but the per-row
caller passes a constant 8,192 rather than any window the model would be served
at; only the pill beside the model already selected takes a real one. GPT4All
has had a `RAM required` column for years, from a figure published in its
catalogue. `lms load --estimate-only`
prices a load from the command line. The column is worth having and should be
presented as the ordinary thing it is.

**The window a model would be served at, before committing, was not found
anywhere.** Every figure in the survey is either a model's ceiling or a window
somebody asked for. The one served-window report found is `ollama ps`, which is
of a model already resident — the position `doctor` already occupies. **And
that a swap costs a load and throws away a cached prefix was found once, in
Claude Code, about a server-side cache and a remote model**: nothing is made
resident there and nothing is let go of. No tool in the survey that holds a
model on the machine it runs on says what a swap costs.

So the report pane's worth is the second and third together, on a machine that
holds the model, and that is what it should be built and described for.

**Nothing here rests on LM Studio's own estimator.** Run on this machine on
2026-08-26, `lms load --estimate-only` returned byte-identical figures for
three models at windows 128 times apart, which contradicts its documentation
and matches what `docs/research/adapter-surfaces.md` already measured for the
other flag that is said to be honoured. Every model here is MLX, so the
finding is bounded to that path. offgrid's own sizing stays the source of the
fit column.

## A profile is written back as the file that was there

The profile file is advertised as hand-editable, and every adapter config
offgrid writes is written once and then left alone for the same reason. A save
that reformatted the file would make that invitation conditional on never
saving — which is what the picker's save key is about to do on every run.

**The values are offgrid's, and everything else in the file is not.** What is
on disk is written over key by key: a key the file names is answered where it
stands, and a key it never named is written after what is there. Comments,
blank lines and the order somebody chose survive, because none of them are
offgrid's to state.

**A file holding a key offgrid cannot act on is written whole instead.** There
is one caller that writes over a file it could not read: `setup` sets a refused
profile aside as `.yaml.rejected` and writes a fresh one over the original. A
measured machine left behind in that file would be refused all over again by
the next read, so it goes — and the comment above it goes with it. Taking the
key alone leaves the comment standing over whatever followed, saying something
false about it. Written whole, the file loses the edits, and the file it lost
them from is the one already set aside beside it.

**What a save produced is checked against what it read, line for line.** A key
written into a section that something follows does not land at the end of that
section: it lands after the blank line and the comment that introduce whatever
is next, so the comment ends up standing over a key it says nothing about.
Reaching into how the parser hangs comments to place the key by hand is more
than this is worth, so the save reads its own output instead — every line of
the file that was there, in order, either untouched or the same key carrying a
new value, and anything new only after the end. Where that does not hold, the
file is written whole. It covers the case above and whichever ones nobody has
thought of yet, which is why it is a check on the result rather than one more
rule about the input.

**A key typed twice is refused rather than read as the last one.** `pyyaml`
took the second and dropped the first without a word. The file is hand-edited,
so two answers to one key is a mistake to report. The parser's own words are
not passed through: they name the line the mapping starts on before the line
the key repeats on, and they close by linking to how the check is switched off,
which is the one thing a person reading it should not do. Offgrid says the
line and what to do about it.

**The file is replaced rather than written into.** It now holds comments and an
order that nothing can write again, so a write that stops halfway through a
file it has already truncated is a loss with nowhere to read it back from. What
a save writes goes to `profile.yaml.writing` and is renamed over the profile,
which is one operation as far as anybody watching is concerned.

**`ruamel.yaml` reads YAML 1.2, where `pyyaml` read 1.1.** An unquoted `yes`,
`no`, `on` or `off` is now the word rather than a boolean. It is the better
reading for a hand-edited file — `host: no` was a machine called `False` — and
the one case offgrid had written a guard for, a window typed as `yes`, is still
refused, now for saying a word where a number belongs.

**`ruamel.yaml` replaces `pyyaml`, rather than joining it.** PyYAML parses to
plain mappings and loses everything around them, so there is no round-trip to
be had from it; keeping both would leave two answers to what YAML this project
reads. It is the whole dependency change: the profile is the only YAML offgrid
writes.

The library is named in `domain/profile/keeping.py` alone, errors included.
Everything else asks for a mapping or a piece of text, so it is one module's
business — including the tests, which read and write the profile through the
same two calls.

## How a model is downloaded is the runtime's own sentence

`recommend` names models off a published table and stops there, so a person
reading it is left with a name and nowhere to type it. The next step is
unambiguous and it is runtime-specific, so the `Runtime` port states it:
`describe_model_download(name)`, free text, naming the model it is about.

Free text because the honest answer differs in kind between runtimes. Where a
command exists it is the answer; where none does, the runtime's own interface
is. LM Studio has both, and says both, application first: the search is what
everybody who has LM Studio has, and `lms get` is what somebody who has
bootstrapped the CLI can paste. offgrid does not require `lms` on the `PATH`,
so the command is offered under the sentence rather than instructed as the way.

**No window name and no keyboard shortcut.** LM Studio's documentation names a
Discover tab reached with ⌘2; the application installed on this machine ships
as Bionic 1.0.4, off the same codebase, where the same search is a modal opened
from a button and ⌘2 does nothing. A gesture that is right on one version and
silently wrong on another is worse than the sentence that holds on both, so
what is named is the application and the model.

**It is said unconditionally, not only for a model the runtime does not have.**
Answering "do you have this one?" would cost `recommend` the one property that
makes it safe to run — it reaches one page and nothing else — and it would put
a leaderboard's `Qwen3.6-35B-A3B` against a catalogue's `qwen/qwen3.6-35b-a3b`
and call the match. Fuzzy matching a vendor's naming is a sub-problem with no
good failure: hide the instruction for a model somebody does not have, or print
it for one they do. Whether a model is held belongs to the picker, which is
connected to the runtime and shows it per row.

**One instruction rather than one per row.** The sentence is the same with a
different name in it, and a table carrying it under every row is a table nobody
reads. The model worked through is the one the ranking put first, so the name
in it is a name on the screen. Nothing is said where nothing was ranked: there
is no model to name, and an instruction naming none is the generic sentence the
conformance suite refuses of an adapter.

**It is a registry entry, not a member of the `Runtime` port.** How a model is
downloaded is a fact about a runtime rather than about a connection to one: it
takes a name, reaches nothing, and wants no address. On the port it cost
`recommend` a connection it had no use for, left `LMStudio` with a method that
never read `self`, and forced an exception into the port's own rule that a
method reaches the server. So it is `MODEL_DOWNLOAD_INSTRUCTIONS` in
`runtimes/__init__.py`, keyed by `RuntimeName` beside the two mappings already
there, and `tests/test_architecture.py` refuses a name missing from any of the
three.

What that costs is a third thing a second adapter registers, and a conformance
row that moved out of the suites over a connection into one over the registry.
What it buys is that nothing is opened to print a sentence. The alternative
considered and dropped was hanging it on `RuntimeConfig`, which needs no third
mapping — but a config is what an adapter is built from, taken from a person's
file, and prose for a reader is not that.

**Which runtime is asked comes from the profile, and from `setup`'s default
where there is no profile.** Somebody running `recommend` before anything else
is exactly who the sentence is for, and refusing them over a file they have not
been told to write yet would answer the wrong question. A profile that is there
and will not load is refused the way every other command refuses it: it names a
runtime, and guessing past what it says would answer about an adapter its owner
did not choose.

**The lines are the adapter's, and nothing reflows them.** A command is one of
the answers the port takes, and a command wrapped by whoever prints it stops
being one that can be copied. So an adapter writes its own line breaks and the
conformance suite holds each line to a width, rather than the printer reflowing
prose it cannot tell from a command.

Binding the runtime costs nothing: opening a connection binds an address, and
this asks it for words. `recommend` still reaches one page.

## The picker lists what is downloaded, and cannot say what it weighs

The model row was specified as identifier, held, size on disk, ceiling and
whether it fits this machine. Two of those five have no source, measured
against the LM Studio running here — 1.0.4, on `127.0.0.1:1234`:

| Asked | What came back |
|---|---|
| `/api/v0/models` | `id`, `type`, `publisher`, `arch`, `compatibility_type`, `quantization`, `state`, `max_context_length`, `capabilities` |
| `/api/v0/models/{id}` | the same fields, for one model |
| `/v1/models` | `id`, `object`, `owned_by` |
| `GET /system` | `Unexpected endpoint or method` — the SDK's namespace is not served here |

No byte count anywhere, and `fits` is a comparison against one, so both columns
go. Three ways to have them were weighed and dropped:

**Parse a parameter count out of the identifier**, and weigh it at the
`quantization` the catalogue does state. Cheap, needs no new port member, and
wrong in a way that is presentable: `gemma-4-e4b` is an effective 4B rather
than 4B of weights, and a number nobody published is exactly what this project
exists not to print.

**Have the adapter measure the model directory.** The mapping does not hold on
the machine it was checked on: the catalogue says `qwen/qwen3.6-35b-a3b`, the
disk says `lmstudio-community/Qwen3.6-35B-A3B-MLX-4bit`, and the publisher
differs between the two. The catalogue is also the coarser of the pair: it
lists one `qwen/qwen3.6-35b-a3b` where the disk holds both a `-MLX-4bit` and a
`-MLX-8bit` directory, so one identifier answers for two builds of different
sizes. Most rows would answer nothing, so the column would be mostly blank.

**Require `lms`**, which prints the figure. That reverses the decision above
that offgrid does not require it on the `PATH`, and reversing a decision to
gain a column is not a trade this feature is worth.

So the row is identifier, held and ceiling, and the two that are missing are
tracked with the measurement above beside them. `recommend` is unaffected: it
sizes what a published list names, from parameter counts that list publishes,
and never asks the runtime what a file weighs.

**Nothing-that-fits goes with them.** It was specified as its own state beside
nothing-downloaded, and it cannot be computed without the fit it is named for.
Nothing-downloaded stays, and is what the picker says today.

## A pairing is an agent and a model, and the runtime is listed rather than picked

`Assembly` names the two the picker can move between. The runtimes list shows
every name offgrid has an adapter for, which is one, and the profile's is the
only one there is a config to assemble from — so a third field would be a
number that could never be anything but its own default.

The day there is a second runtime, this is where it lands, beside the model
row's columns and the dialect-refusal pane that were already named as the two
surfaces that move.

## The report is `doctor`'s, with what a keystroke costs said under it

Everything down to `conversations` is the report the command prints, asked for
part by part from the same place — `describe_the_runtime`, `describe_the_model`,
`describe_what_is_requested`, `describe_the_agent` and
`describe_a_discarded_window`, which are the five `describe_what_was_read`
itself composes — against a profile the pairing was written into rather than
against the file. Under it, one block the screen owns: whether this pair can
talk, whether the agent is here at all, and whether starting it costs a load.

Said under rather than woven in, because the two are read by different
questions — what a run was told, and what a key would do — and because a screen
that edited the middle of `doctor`'s report is a screen that comes to word one
fact differently. `tests/test_picker.py` compares everything above that block
against what `doctor` prints, line for line.

**Sitting on the model the runtime is already holding is read as asking for
nothing — and only where the profile asks for nothing.** The two describe the
same run there, and the difference is only what a save would write down:
somebody who has moved the highlight nowhere has named no model, and
materialising one under them would be a request they did not make. Where the
profile does name a model, the highlight and the file are two statements and
the highlight is the one somebody just made, so the report follows it.

**The window of a model that is not held reads `unknown`, not `unstated`.** The
two mean different things and the report has always drawn the line: `unstated`
is what a held model says when the runtime answers no number for it, and a cold
model is not being served at all, so the number does not exist yet.
`describe_the_model` takes whether the model is held for that reason — `doctor`
reads its model off what is held and passes `True`; the picker reports on a
model somebody is only looking at.

## A row the cursor may not reach is the widget's guarantee

Absent agents are `OptionList` options with `disabled` set, so stepping over
them is what the widget does rather than a refusal on select that somebody can
forget to write. What it costs is that such a row cannot be highlighted, so its
report is reached only where the profile names that agent — which is the case
that matters, since that is the agent a run would try to start.

Where the profile names an agent this machine has not got and another is here,
the highlight opens on the one that is here. The report says which pairing it
is about, and the absent row still says `not installed` beside its name.

**The two acceptance criteria this trades between are in tension**, and the
trade is recorded rather than hidden: "unreachable by the cursor" and "its
report says where to get it" cannot both hold for an agent nobody can highlight.
Unreachable won, because arming an agent that is not here is the exit 127 the
screen exists to prevent, and the report is reached in the case that matters —
the agent a run would actually try to start. Someone browsing for where OpenCode
comes from reads `not installed` on the row and nothing more.

## What there is to pick from, and what one pick would do, are two modules

`assembling.py` running past 500 lines was what prompted the look, but the
number is not what decided it. There is a seam: the values, the row layouts and
the ordering are the list of what there is, and the report is what one of them
would do — two different questions, and `costing.py` reaches for the first
while nothing goes the other way. Cutting there leaves each file at about 280
lines and about one thing. No exact counts here, because this branch's own
later commits moved them twice.

The split that was considered and rejected was by length alone, down the middle
of the report: it would have put the pricing block in one file and the lines it
sits under in another, so a reader following one report would open two files
and neither would be about a whole idea.

Three files still run past 200 and stay whole, which the rule asks be said
rather than fixed by splitting. `tests/test_picker.py`, the longest, is one
seam — the screen — and a suite is read by opening the test named after the
behaviour rather than by reading down. `picker.py` is one screen: its
composition, its two dropdowns and models list, and the keys over them are the
same idea, and a file holding half a screen is a file nobody can read the
layout out of.
`checkup.py` grew by having its parts made reachable, which is what let a
second surface stop duplicating them.

## The runtime and agent are dropdowns, the models a list

The runtime and the agent are dropdowns rather than full-height lists: each has
two or three choices, and a box sized for a list of them is mostly empty air
the models list could use. A dropdown holds one line closed and opens to a
foreground popup, which is what a person expects of a choice with few options.
The models stay a full list — it is the one a person shops in, it runs long,
and it wants its columns and its held marks on screen at once.

**The popup greys what a run cannot start.** Textual's `Select` cannot mark an
option, so its cursor would land on an agent this machine has not got — the
exit 127 the screen exists to prevent. `Dropdown` overrides the one method
`Select` leaves between its options and the overlay they are shown in,
`_setup_options_renderables`, to disable those rows; a disabled row is what the
cursor steps over, the same guarantee the models list has. It is a private
method, so a test drives the whole gesture — open, walk, commit — and would go
red if a Textual upgrade moved it.

**The report follows the committed pick, not the open popup.** `Select` says a
value changed on commit rather than as the highlight moves inside the overlay,
which is what a popup does: a person opens it, chooses, and reads the report
for what they chose. The models list, always open, still recomputes as its
highlight moves.

**Native `Select` was measured and rejected**: it shows an absent agent as an
ordinary, selectable row, which is the hole the guard closes. Building the
popup by hand was not considered — the override is six lines and rides on the
overlay already being an `OptionList`.

The widget that greys a choice is its own file, `dropdown.py`: it is a `Select`
subclass with no knowledge of runtimes or agents, reusable by anything that
offers a choice some of which cannot be taken, and it is what the screen's own
tests reach for by name. What is left in `picker.py` is one screen — its
composition, the keys over it, and how it reads a pick — at about 390 lines.

## The runtime dropdown is not yet a real choice

The agent dropdown greys what this machine has not got, checked per agent. The
runtime dropdown does not: it lists every runtime offgrid drives and greys all
but the profile's, because only the profile's is connected and read, and the
whole report is about that one runtime. Selecting another would change nothing,
so the others are greyed.

Making the runtime a real choice — a presence check per runtime, and a report
that re-reads the selected runtime's catalogue, held models and dialects — is
deferred to #205. What "a runtime is installed" means is a contract that
belongs to the runtime adapter, and it is only got right against two runtimes;
built against LM Studio alone it is a guess the second may not fit. So it rides
with the second runtime rather than being designed blind now.
