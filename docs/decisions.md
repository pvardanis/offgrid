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
