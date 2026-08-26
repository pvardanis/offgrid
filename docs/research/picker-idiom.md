# What terminal pickers actually bind, say and hand back

Primary-source research, gathered 2026-08-26. Everything below records what a
project's own source says, what its documentation states, or what a program on
this machine printed when it was run. Where a claim rests on reading source, the
repository and path are named, and symbols rather than line numbers, so that the
pointers survive the code moving. Where a documented claim and a measured one
disagree, both are recorded, marked as such, rather than one being written over
the other.

It is **not** a recommendation about offgrid's design. There is no proposed
keymap here, no widget choice, no argument for or against any shape the picker
might take. offgrid's shape is already settled from facts about offgrid: it is a
launcher that assembles a profile, exits before the agent starts, never wraps
the agent's terminal in a pty, and never holds or lets go of a model itself.
Nothing surveyed here bears on that, and several of the tools below are shaped
quite differently for reasons of their own. The six questions are answered so
that someone else can tell which conventions are settled, which are contested,
and which do not exist.

Two things follow from the survey and are worth stating once at the top rather
than repeating in every section. First, **most of the agent tools are full
session TUIs** — Claude Code, OpenCode and Cline all own the screen for the
length of a conversation, and their model pickers are dialogs inside that
session, not programs that exit. That is a fact about them, recorded as such.
Second, genuine pick-then-exit prior art is thinner than it looks: of the
surfaces asked about, only fzf and `gum choose` really pick a value, print it
and leave.

## What was read, and at which version

| Thing | Version | How that was determined |
| --- | --- | --- |
| fzf | newest release **v0.74.3**, 2026-08-17; source read at **`f7ae439f`**, 2026-08-21 | `gh api repos/junegunn/fzf/releases/latest`; `git clone --depth 1`, `git log -1`. Behaviour read from `man/man1/fzf.1` and `src/options.go` on `master` |
| gum | newest release **v2.0.0**, 2026-08-20; source at **`4d089f95`** | `gh api repos/charmbracelet/gum/releases/latest`; clone of `charmbracelet/gum`. Not installed on this machine |
| gh-dash | newest release **v4.25.2**, 2026-07-10; source at **`4ea7c39f`**, 2026-08-01 | `gh api repos/dlvhdr/gh-dash/releases/latest`; clone |
| lazygit | newest release **v0.64.1**, 2026-08-12; source at **`ea916395`**, 2026-08-18 | `gh api repos/jesseduffield/lazygit/releases/latest`; clone |
| k9s | newest release **v0.51.0**, 2026-06-06; source at **`2582cc71`**, 2026-08-25 | `gh api repos/derailed/k9s/releases/latest`; clone |
| OpenCode | newest release **v1.18.23**, 2026-08-25; source at **`1cc53890`**, 2026-08-26 | `gh api repos/sst/opencode/releases/latest`; clone. State file read from this machine |
| Claude Code | docs current as of the fetch; behaviours pinned to versions **v2.1.144 – v2.1.242** in the prose | `code.claude.com/docs/en/model-config` and `/prompt-caching`, which version-stamp individual behaviours inline. Closed source, so nothing was read |
| Cline | repository last pushed 2026-08-26; newest release **desktop-v0.0.19**, 2026-08-26 | `gh api repos/cline/cline`; files read individually through `gh api .../contents/...` rather than cloned |
| Textual | **8.2.8**, released 2026-06-30; source at **`06dbeef4`**, 2026-07-11, whose `pyproject.toml` also says `8.2.8` | `gh api repos/Textualize/textual/releases/latest`; clone |
| toolong | newest release **v1.4.0**, 2024-03-02; source at **`5aa22ee8`**, 2024-04-28, `pyproject.toml` says `1.5.0` | `gh api repos/Textualize/toolong/releases/latest`; clone. Dormant for two years |
| harlequin | newest release **v2.10.0**; source last committed 2026-08-25 | `gh api repos/tconbeer/harlequin/releases/latest`; clone. `pyproject.toml` pins `textual==8.2.8` |
| Jan | newest release **v0.8.4**, 2026-07-23; source at **`95e96d02`**, 2026-08-25, `src-tauri/tauri.conf.json` says `0.8.4` | `gh api repos/menloresearch/jan/releases/latest`; clone |
| GPT4All | newest release **v3.10.0**, 2025-02-25; source at **`b666d16d`**, last pushed 2025-05-27 | `gh api repos/nomic-ai/gpt4all/releases/latest`; clone. Dormant for fifteen months |
| llama-swap | newest release **v251**, 2026-08-23; source at **`8a32e055`**, 2026-08-24 | `gh api repos/mostlygeek/llama-swap/releases/latest`; clone |
| Ollama | newest release **v0.33.0**, 2026-08-21; source at **`e2c6c7e8`**, 2026-08-25; the app on this machine reports **0.32.15** | `gh api repos/ollama/ollama/releases/latest`; clone; the app's own startup log |
| LM Studio | docs repo at **`43a80e9d`**, 2026-08-18; `lms` on this machine reports **CLI commit `71bd99c`** | clone of `lmstudio-ai/docs`; `lms version`. The app version was not read this session; `docs/research/adapter-surfaces.md` records it at 0.4.20 as of 2026-08-11 |
| WCAG 2.2 | the published Recommendation | `w3.org/TR/WCAG22` and the matching Understanding documents |

Two measurements were taken on this machine rather than read. `lms load
--estimate-only` was run against four local models at several context lengths;
nothing was loaded. `ollama list` was run, and **it started the Ollama app** —
Ollama's CLI launches the app rather than refusing when the server is not up,
which section 4 explains. No model was loaded and nothing was written; the app
was left running.

## 1. Pick-then-exit prior art

### Which of these actually exit

| Surface | Shape | What leaves it |
| --- | --- | --- |
| fzf | **pick-then-exit** | the selection on stdout; optionally the key that confirmed |
| `gum choose` | **pick-then-exit** | the selection on stdout |
| `lms load` with no model key | **pick-then-act** | nothing; it loads the chosen model in the same process |
| gh-dash | resident dashboard | nothing; it is the application |
| lazygit | resident dashboard | nothing |
| k9s | resident dashboard | nothing |
| Claude Code `/model` | dialog inside a resident session TUI | a model selection applied to the running session |
| OpenCode's model dialog | dialog inside a resident session TUI | a model selection applied to the running session |
| Cline's model selector | dropdown inside a resident VS Code webview | a settings value |

Only the first two are prior art for a surface that assembles a value and hands
it to a caller. The rest are recorded because they were asked about, and because
their keymaps and their absent-row and error conventions are worth having even
where their handoff is not.

### fzf

Defaults are documented in the `KEY/EVENT BINDINGS` section of
[`man/man1/fzf.1`](https://github.com/junegunn/fzf/blob/master/man/man1/fzf.1),
under the heading `ACTION: DEFAULT BINDINGS (NOTES):`. Verbatim, with fzf's own
formatting stripped:

```
abort                        ctrl-c  ctrl-g  ctrl-q  esc
accept                       enter   double-click
toggle+down                  ctrl-i  (tab)
toggle+up                    btab    (shift-tab)
down                         ctrl-j  down
```

Four keys abort. There is no `?` help binding and no footer: fzf has a `--header`
for arbitrary text and an info line for match counts, and it documents its keys
in the man page rather than on screen. `cancel` — "clear query string if not
empty, abort fzf otherwise" — exists as an action but is not bound by default.

The handoff is the interesting part, and fzf has three mechanisms for it.

**The selection goes to stdout and the exit code says what happened.** From the
`EXIT STATUS` section: `0` normal exit, `1` no match, `2` error, `126` and `127`
for a `become` action's command, `130` "Interrupted with CTRL-C or ESC".

**`--expect` reports which key confirmed.** This is the closest thing in the
survey to a surface that distinguishes two kinds of confirmation:

> Comma-separated list of keys that can be used to complete fzf in addition to
> the default enter key. When this option is set, fzf will print the name of the
> key pressed as the first line of its output (or as the second line if
> `--print-query` is also used). The line will be empty if fzf is completed with
> the default enter key.

The man page also gives the newer equivalent, which composes with `--bind`:

```
fzf --multi \
    --bind 'enter:print()+accept,ctrl-y:select-all+print(ctrl-y)+accept'
```

**`become(...)` replaces fzf with the chosen command.** From the same page:

> `become(...)` action is similar to `execute(...)`, but it replaces the
> current fzf process with the specified command using `execve(2)` system call.

listed in the action table as "replace fzf process with the specified command".

### gum choose

Bindings are constructed in
[`choose/choose.go`](https://github.com/charmbracelet/gum/blob/main/choose/choose.go),
each with the help string it shows:

| Keys | Help string |
| --- | --- |
| `enter`, `ctrl+q` | `enter submit` |
| `esc` | `esc quit` |
| `ctrl+c` | `ctrl+c abort` |
| space, `tab`, `x`, `ctrl+@` | `x toggle` |
| `a`, `A`, `ctrl+a` | `ctrl+a select all` |
| arrow keys | `←↓↑→ navigate` |

The help line is on by default: `ShowHelp` in `choose/options.go` carries
`default:"true"` and the environment variable `GUM_CHOOSE_SHOW_HELP`. The header
defaults to the literal string `"Choose:"`, the cursor to `"> "`, the selected
prefix to `"✓ "` and the unselected to `"• "`. Abort exits `130`
(`internal/exit/exit.go`, `StatusAborted`), matching fzf.

Note that `enter` and `esc` mean different things here — submit and quit — while
in fzf `esc` is one of four aborts and `enter` accepts. The two agree on
`enter` and on `ctrl+c`; they disagree about `esc` only in name, since gum's
"quit" also produces no selection.

### `lms load` with no argument

`lms load --help` on this machine documents the positional argument as: "The
model key to load. If not provided, enters an interactive mode to select a
model." The published docs say the same for `lms unload`: "If not provided, you
will be prompted to select one"
([`3_cli/0_local-models/load.md`](https://github.com/lmstudio-ai/docs/blob/main/3_cli/0_local-models/load.md)).
The picker was not driven, because doing so would have loaded a model. Its
keymap is therefore not established here.

This is a picker that acts rather than a picker that hands a value back: the
same process goes on to load the model.

### gh-dash

Keys are declared in
[`internal/tui/keys/keys.go`](https://github.com/dlvhdr/gh-dash/blob/main/internal/tui/keys/keys.go)
as a `KeyMap` of `key.Binding`s, each with `key.WithHelp(display, description)`.
The literal pairs:

```
↑/k     move up            ↓/j     move down
g/home  first item         G/end   last item
p       toggle preview     P       toggle preview position
o       open in GitHub     r       refresh          R  refresh all
Ctrl+d  preview page down  Ctrl+u  preview page up
/       search             y       copy number      Y  copy url
?       help               q       quit
```

`Quit` binds `q` and `ctrl+c` but displays only `q`. There is no select or
confirm binding at all, which is what makes it a dashboard: `o` opens the
highlighted item in a browser and gh-dash carries on running.

The footer convention is worth naming because it is unusually spare.
`KeyMap.ShortHelp()` returns `[]key.Binding{k.Help}` — one entry. The always-on
footer therefore reads `? help` and nothing else, and every other key appears
only when `?` expands the full help, which `FullHelp()` groups into navigation
keys, app keys, view-specific keys, custom keys, and quit-and-help.

### lazygit and k9s

Both are resident, both bind `q` to quit and `?` to help, and neither has a
confirm-and-exit key, for the same reason gh-dash does not. Their interesting
behaviour is in sections 3 and 4.

### Claude Code's `/model`

Two keys are documented, and they are the answer to question 2 as well:

> In the picker:
>
> * `Enter`: switch model and save as your default
> * `s`: switch model for this session only

The picker is reached with `/model` and no argument, from inside a running
session; typing `/model <name>` "behaves like `Enter`". Rows can carry a label —
`Requires usage credits` on the Fable 5 row, `Set by ANTHROPIC_DEFAULT_MODEL` on
the Default row — and, on the Anthropic API, a price. The price "is a display
label only; it doesn't affect which model a row selects or what your provider
bills."

### OpenCode's model dialog

The dialog is `DialogModel` in
`packages/tui/src/component/dialog-model.tsx`, rendering the reusable
`DialogSelect` from `packages/tui/src/ui/dialog-select.tsx`. Keys come from
`packages/tui/src/config/keybind.ts`, where each is declared with its default
and its description:

```
"dialog.select.prev":      "up,ctrl+p"   Move to previous dialog item
"dialog.select.next":      "down,ctrl+n" Move to next dialog item
"dialog.select.page_up":   "pageup"      Move up one page in dialog
"dialog.select.page_down": "pagedown"    Move down one page in dialog
"dialog.select.home":      "home"        Move to first dialog item
"dialog.select.end":       "end"         Move to last dialog item
"dialog.select.submit":    "return"      Submit selected dialog item
model_provider_list:       "ctrl+a"      Open provider list from model dialog
model_favorite_toggle:     "ctrl+f"      Toggle model favorite status
model_list:                "<leader>m"   List available models
app_exit:                  "ctrl+c,ctrl+d,<leader>q"  Exit the application
```

`DialogSelect` also binds `tab` and `shift+tab` to move between the dialog's
actions, described as `Next dialog action` and `Previous dialog action`.

Filtering is a text input at the top of the dialog rather than a key: the
dialog's own `onFilter` feeds a `fuzzysort` search over `title` and `category`,
weighted "prioritize title matches (weight: 2) over category matches (weight:
1)" per the comment in `dialog-select.tsx`.

There is no footer of keys. The dialog's header is the title on the left —
`"Select model"`, or the provider's name when the dialog was opened for one
provider — and, on the right, the literal string `esc`, which is also a mouse
target that closes the dialog. Actions the dialog offers are listed at its
bottom by title: `Connect provider` or `View all providers`, and `Favorite`.

### Cline

`apps/vscode/webview-ui/src/components/settings/common/ModelSelector.tsx` is a
`VSCodeDropdown` with the label `Model`, a first option reading `Select a
model...`, and one option per model id. No keys of its own, no footer; it is an
HTML select inside a webview panel that stays open. A sibling `ModelInfoView.tsx`
renders the selected model's context window compactly — the comment gives
`"200K"` as the example — alongside per-million-token prices.

## 2. Save-vs-use

Three of the tools distinguish "use this once" from "make this my default", and
they do it in three different ways.

### Claude Code: two keys, and the polarity has changed once

From
[`code.claude.com/docs/en/model-config`](https://code.claude.com/docs/en/model-config),
in the *Setting your model* section:

> As of v2.1.153, `/model` saves your choice as the default for new sessions by
> writing the `model` field in your user settings. In the picker:
>
> * `Enter`: switch model and save as your default
> * `s`: switch model for this session only
>
> Typing `/model <name>` directly behaves like `Enter`. A model set with
> `/model` in non-interactive mode, with the `-p` flag, applies to the current
> session only and isn't saved as your default.

and, immediately after:

> In v2.1.144 through v2.1.152, `/model` applied to the current session only and
> `d` in the picker saved a default.

So the convention was `d` for save with `Enter` meaning this-session-only, and
became `Enter` for save with `s` meaning this-session-only, within nine patch
versions. That is the only evidence in the survey of a project moving an
explicit save between keys, and it moved in the direction of making the
persistent action the default one.

The destination is named: **the `model` field in the user settings file**, which
is `~/.claude/settings.json`. On this machine that file has no `model` key,
which is consistent with `/model` never having been used here to save one.

`--model` is documented as the other half of the pair:

> The `--model` flag and `ANTHROPIC_MODEL` environment variable apply only to
> the session you launch with them. To run different models in different
> terminals at the same time, launch each one with its own `--model` flag rather
> than switching with `/model`.

The full precedence order, from the same page, is `/model` during a session,
then `--model` at startup, then `ANTHROPIC_MODEL`, then the `model` setting,
then `ANTHROPIC_DEFAULT_MODEL`. A choice saved with `/model` beats
`ANTHROPIC_DEFAULT_MODEL` on later launches, but not project or managed
settings, which "reapply on the next launch".

### OpenCode: no save key, and it persists anyway

OpenCode has no save-versus-use split, because selecting a model in the dialog
persists as a side effect and nothing is said about it.

`DialogModel.onSelect` calls `local.model.set({ providerID, modelID }, { recent:
true })`. In `packages/tui/src/context/local.tsx`, the model store's `save()`
writes `recent`, `favorite` and `variant` to `model.json` under the state
directory, atomically. That directory is `xdgState/opencode`
(`packages/core/src/global.ts`), which on this machine is
`~/.local/state/opencode`. The file exists here and reads, in part:

```json
{"recent":[{"providerID":"lmstudio","modelID":"qwen/qwen3.6-27b"},
           {"providerID":"lmstudio","modelID":"qwen/qwen3.6-35b-a3b"},
           {"providerID":"ollama","modelID":"qwen3.6:latest"}],
 "favorite":[], "variant":{...}}
```

That list is not merely a history. `fallbackModel` in the same file resolves the
next session's model in this order: the `--model` argument, then the `model` key
in the config, then **the first valid entry in `modelStore.recent`**, then the
provider's default or its first model. So picking a model in the dialog decides
what the next session starts on, unless a flag or the config file names one.

Two things follow. The config file, `opencode.json`, is never written by the
dialog — the persistence is entirely in the state file. And nothing on screen
says any of this happens: there is no key to press, no confirmation, and no
label. It is the opposite convention to Claude Code's, arrived at by a different
route.

### Cline

The selector is a settings control: `onChange` writes the value into Cline's
API configuration. There is no this-time-only variant of it and no explicit save
key — the same shape as any settings field in a preferences pane.

### How an explicit save is keyed elsewhere

Only one keyed save was found in the survey, and it is Claude Code's `s`. `w`
and `ctrl+s` were looked for in fzf, gum, gh-dash, lazygit, k9s and OpenCode and
appear in none of them with a save meaning: gh-dash has no write action at all,
lazygit's `s` is stash, and OpenCode's `ctrl+f` toggles a favourite, which is a
preference rather than a default. The evidence for what letter a save takes in a
terminal picker is therefore one data point, and that data point moved once.

## 3. Absent and disabled rows

The conventions in use are: hide the row, dim the row, mark the row with a text
label, or put it in a section of its own. All four are in the survey, and two of
the tools use more than one at once.

### Hiding

**Claude Code hides administratively excluded rows.** From `model-config`:

> Claude Code hides excluded models from the `/model` picker.

referring to models excluded by an `availableModels` allowlist in managed
settings. Where a model is unavailable for a different reason, the same page
records both behaviours as possible: Fable 5 "is not available under zero data
retention, where the `/model` picker either omits it or shows it disabled."
Under an older Claude Code version, "Older versions do not show Fable 5 in the
model picker and cannot select it."

**OpenCode hides disabled options.** `DialogSelect` carries a `disabled` field
on each option, and its `filtered` memo drops them before anything is rendered:

```ts
if (props.skipFilter || props.renderFilter === false)
  return props.options.filter((x) => x.disabled !== true)
const options = pipe(props.options, filter((x) => x.disabled !== true))
```

`DialogModel` sets `disabled: provider.id === "opencode" && model.id.includes("-nano")`,
so those models never appear. Note that the `disabled` styling in the same file
— rendering with `theme.textMuted` — applies to the dialog's *actions*, not to
its options; an option marked disabled is never drawn at all.

### Dimming

**Textual's `OptionList` dims and skips.** `Option` takes
`disabled: bool = False`, documented in
`src/textual/widgets/_option_list.py` as "Disable the option (will be shown
grayed out, and will not be selectable)". The rendering path swaps the component
class to `option-list--option-disabled`, whose default CSS is `color:
$text-disabled`. Colour is the only difference: no prefix, no suffix, no glyph.

The skipping is the more consequential half. `action_cursor_up` and
`action_cursor_down` are documented as moving "to the previous enabled option"
and "to the next enabled option" and call `_widget_navigation.find_next_enabled`;
`action_first` and `action_last` call `find_first_enabled` and
`find_last_enabled`; `_move_page` uses `find_next_enabled_no_wrap`. So the
highlight cannot come to rest on a disabled row. `watch_highlighted` posts
`OptionHighlighted` only when the newly highlighted option is not disabled, and
`action_select` posts `OptionSelected` only when it is not disabled. A disabled
row in a Textual `OptionList` is visible, dim, unreachable by the cursor, and
silent.

`ListView` behaves the same way: `_list_view.py` skips `ListItem`s whose
`disabled` is set when moving the index.

`DataTable` has no per-row disabled concept at all. `disabled` appears in
`_data_table.py` only as the widget-level `Widget.disabled` passed through
`__init__` — there is nothing to disable a row or a cell with.

**Textual's `Footer` dims unavailable keys** rather than removing them:
`Footer.compose` builds a `FooterKey` per shown binding with `disabled=not
enabled`, taking `enabled` from `screen.active_bindings`.

### Marking with text

**GPT4All puts a `RAM required` column on every row and a warning under the ones
that exceed the machine.** In `gpt4all-chat/qml/AddGPT4AllModelView.qml`,
`AddHFModelView.qml` and `ModelsView.qml`, all three carry the same pair: a
label `qsTr("RAM required")` with the value `qsTr("%1 GB").arg(ramrequired)` or
`qsTr("?")` when unknown, and a banner whose visibility condition is
`LLM.systemTotalRAMInGB() < ramrequired` and whose text is

> WARNING: Not recommended for your hardware. Model requires more memory (%1 GB)
> than your system has available (%2).

The row stays selectable. GPT4All warns and lets you proceed.

**Claude Code labels rows.** `Requires usage credits` appears on the Fable 5 row
when the plan bills that way; `Set by ANTHROPIC_DEFAULT_MODEL` appears on the
Default row when that variable resolves it. Both are text on the row rather than
a colour.

**Jan uses an icon, a word and a colour together.** `TRIGGER_STYLES` in
`web-app/src/containers/ModelInfoHoverCard.tsx` gives each of four tiers an
icon, a label, a detail sentence and a colour:

| Tier | Icon | Label | Detail |
| --- | --- | --- | --- |
| green | `IconCheck` | `Fits` | `Should run comfortably on your device` |
| yellow | `IconAlertTriangle` | `May be slow` | `Will run but leaves little memory headroom` |
| red | `IconX` | `Won't fit` | `Likely exceeds your available memory` |
| unknown | `IconDeviceDesktopQuestion` | `Fit unknown` | `Could not estimate memory requirements` |

The pill carries `aria-label={`Device compatibility: ${style.label}`}`. The row
remains selectable at every tier, `Won't fit` included.

### Sectioning

**OpenCode groups rather than sorts.** `DialogModel` builds options with a
`category` field, and when there is no search needle the list is `Favorites`,
then `Recent`, then one section per provider, then `Popular providers` for
someone with no provider connected. Typing collapses the sections into a flat
fuzzy-ranked list.

### Accessibility guidance on colour-only marking

WCAG 2.2 has a criterion directly on the point.
**Success Criterion 1.4.1 Use of Color**, verbatim:

> Color is not used as the only visual means of conveying information,
> indicating an action, prompting a response, or distinguishing a visual
> element.

It carries no exception for disabled or inactive components. Its Understanding
document notes that the criterion "aims to ensure that sighted users who cannot
distinguish between some colors can still understand content" and "does not
directly address the needs of users with assistive technologies".

The two contrast criteria are where inactive components are carved out, and they
are carved out asymmetrically. **1.4.3 Contrast (Minimum)** requires 4.5:1 for
text with an *Incidental* exception: "Text or images of text that are part of an
inactive user interface component ... have no contrast requirement." **1.4.11
Non-text Contrast** requires 3:1 for "Visual information required to identify
user interface components and states, **except for inactive components** or
where the appearance of the component is determined by the user agent and not
modified by the author".

So the standards permit a dim disabled row to be dim — there is no contrast
floor it must clear — while 1.4.1 still asks that whatever the dimness is
telling you also be told some other way. Textual's `OptionList` marks a disabled
row by colour alone; Jan's pill and GPT4All's warning both pair colour with
words.

## 4. Empty and error states against a local server

### Where the message goes

Two conventions, split by whether the failure happens before the surface opens
or during it.

**lazygit handles its startup failure in plain text, before the TUI.** Outside a
git repository, `pkg/app/app.go` switches on the `notARepository` user config,
whose values are `prompt`, `create`, `skip` and `quit`. The default is `prompt`,
and it writes to the terminal and reads a line from stdin:

```
Not in a git repository. Create a new git repository? (y/N):
Branch name? (leave empty for git's default):
```

Under `quit` it writes `Error: must be run inside a git repository` to stderr and
exits `1`; under an unrecognised value, "The value of 'notARepository' is
incorrect. It should be one of 'prompt', 'create', 'skip', or 'quit'." Strings
are from `pkg/i18n/english.go`. The full-screen surface never opens in any of
these cases.

**k9s handles connection loss inside the running surface, on a status line.**
`App.refreshCluster` in `internal/view/app.go` polls `Conn().CheckConnectivity()`
on a `clusterRefresh` interval. On failure it stops the current view's refresh
and increments a retry counter; on recovery it posts `a.Status(model.FlashInfo,
"K8s connectivity OK")` and restarts the view. The message is a flash on the
status line, which `internal/ui/flash.go` prefixes with an emoji per level.

### Whether it retries, and whether it gives up

k9s does both. The retry loop uses a `backoff.NextBackOff()` and calls
`a.BailOut(1)` when it returns `backoff.Stop`. Separately, once the retry count
reaches the configurable `MaxConnRetry`, it logs "Conn check failed. Bailing
out!" and sets

```go
ExitStatus = fmt.Sprintf("Lost K8s connection (%d). Bailing out!", count)
```

So k9s stays open and retrying for a bounded number of attempts and then closes,
printing that line. It is the only surface in the survey that retries a
connection on its own.

### Whether more than one cause is named

**Ollama names one, and only after trying to fix it.** `checkServerHeartbeat` in
`cmd/cmd.go` runs before most commands; on a connection error it calls
`startApp`, which on macOS (`cmd/start_darwin.go`) resolves the executable's
symlink, matches it against `^.*/Ollama\s?\d*.app` and runs `open -j -a <app>
--args --fast-startup`. Only when that fails does the user see the one error the
file declares:

```go
var errNotRunning = errors.New("could not connect to ollama server, run 'ollama serve' to start it")
```

Elsewhere, `ollama --version` against a dead server prints `Warning: could not
connect to a running Ollama instance` and carries on. Neither message
distinguishes "not started" from "not installed" from "wrong host".

This behaviour was met directly. `ollama list` was run on this machine and
started the Ollama app rather than failing; its log line reads `msg="starting
Ollama" app=/Applications/Ollama.app version=0.32.15`. No models were installed,
so `ollama list` and `ollama ps` both printed nothing at all — not an empty-state
sentence, just no rows.

### Empty-state wording

**gh-dash** has two. `internal/tui/components/section/section.go` builds

```
No %s were found that match the given filters
```

styled with a dedicated `Section.EmptyStateStyle`, rendered by
`table.go` in place of the rows when `len(m.Rows) == 0`. The detail pane's is
`"Nothing selected..."`, vertically centred (`sidebar.go`).

**llama-swap** has a component whose whole job is this: `ui/src/components/EmptyState.svelte`
renders a `message` prop as a centred `<p>` in muted text, or arbitrary children
instead. It does not itself supply the wording.

**Ollama's own desktop model picker** has no empty state visible in the source:
`app/ui/app/src/components/ModelPicker.tsx` renders a search input with the
placeholder `Find model...`, a trigger reading `Select a model` or `Loading...`,
and a `ModelList` of whatever came back.

### Whether a connection dot carries words

**llama-swap** pairs a coloured dot with a text tooltip.
`ui/src/components/ConnectionStatus.svelte` maps `connected` to emerald,
`connecting` to amber and `disconnected` to red, and sets the container's
`title` to the literal `` `Event Stream: ${$connectionState ?? "unknown"}` ``.
The colour is the only thing on screen; the words are behind a hover.

## 5. Textual's own idioms

Read at 8.2.8 unless noted.

### Default global bindings

`App.BINDINGS` in `src/textual/app.py` is two entries and nothing else:

```python
BINDINGS: ClassVar[list[BindingType]] = [
    Binding(
        "ctrl+q",
        "quit",
        "Quit",
        tooltip="Quit the app and return to the command prompt.",
        show=False,
        priority=True,
    ),
    Binding("ctrl+c", "help_quit", show=False, system=True),
]
```

**`ctrl+q` quits.** It is `priority=True`, so it is dispatched before the focused
widget's bindings, and `show=False`, so it does not appear in the `Footer`.

**`ctrl+c` does not quit.** It runs `action_help_quit`, whose comment in
`app.py` explains itself:

```python
# Doing this because users will reflexively hit ctrl+C to exit
# Ctrl+C is now bound to copy if an input / textarea is focused.
# This makes is possible, even likely, that a user may do it accidentally
```

and whose body searches the active bindings for a quit action and posts a
notification:

```python
self.notify(f"Press [b]{key}[/b] to quit the app", title="Do you want to quit?")
```

`Screen.BINDINGS` binds `ctrl+c,super+c` to `screen.copy_text`, described as
`"Copy selected text"`, `show=False`. So `ctrl+c` copies where a selection
exists and otherwise tells you which key quits.

**`ctrl+p` opens the command palette.** `COMMAND_PALETTE_BINDING: ClassVar[str] =
"ctrl+p"` and `ENABLE_COMMAND_PALETTE: ClassVar[bool] = True`. The binding is
added in `App.__init__` — but only after scanning the app's own bindings for one
whose action is `command_palette` or `app.command_palette`, and skipping if it
finds one. It too is added `priority=True`, `show=False`, with `key_display`
from `COMMAND_PALETTE_DISPLAY` and the tooltip "Open the command palette".

**`escape` is spoken for by default.** `App.ESCAPE_TO_MINIMIZE: ClassVar[bool] =
True`, whose docstring says it is "Use escape key to minimize widgets
(potentially overriding bindings)" and that it is the default used when the
active screen's own `ESCAPE_TO_MINIMIZE` is `None`.

### Which of those are expensive to override

The command palette is the cheapest: set `COMMAND_PALETTE_BINDING` to a
different key, or bind `command_palette` yourself and the automatic binding is
not added, or set `ENABLE_COMMAND_PALETTE = False`. Escape is a class variable
away. `ctrl+q` is a `priority` binding on `App` itself and quitting is what a
Textual user reaches for it expecting: harlequin's `action_bind_keymaps` in
`src/harlequin/app.py` treats it as non-negotiable, seeding

```python
required_bindings = {"quit": "ctrl+q"}
```

and re-adding it after applying a user's keymap unless that keymap bound `quit`
itself. `ctrl+c` is marked `system=True`, documented in `binding.py` as "Make
this binding a system binding, which removes it from the key panel."

### Footer and Header

`Footer` derives itself. `Footer.compose` reads `self.screen.active_bindings`,
keeps the bindings whose `show` is true, groups them by action, groups those by
`Binding.Group`, and mounts one `FooterKey` per entry carrying the key, the
`app.get_key_display(binding)` string, the description and `disabled=not
enabled`. Footer keys are clickable, with a `&:hover` rule and `pointer:
pointer`. There is nothing to write: what appears in the footer is decided by
which bindings the focused widget and its ancestors declare with `show=True`.

`Header` is a fixed arrangement rather than a derived one: a `HeaderIcon` docked
left, whose `on_mount` sets its tooltip to "Open the command palette" or
disables it when the palette is off, a title, and a clock or `HeaderClockSpace`
docked right.

toolong shows what departing from `Footer` looks like: it writes its own
`LogFooter` (`src/toolong/log_view.py`) which reads `app.namespace_bindings`
itself, filters on `binding.show`, and additionally drops the tail key when
`can_tail` is false — hiding an inapplicable key rather than dimming it. Its
bindings set `key_display` explicitly to compact forms: `Binding("ctrl+t",
"toggle_tail", "Tail", key_display="^t")`.

### Selectable rows: which widget does what

| | per-row disabled | cursor skips disabled | select binding |
| --- | --- | --- | --- |
| `OptionList` | yes, `Option(..., disabled=...)` | yes | `enter` → `action_select` |
| `ListView` | yes, `ListItem.disabled` | yes | `enter` |
| `SelectionList` | yes, inherits `Option` | yes | `space` toggles |
| `DataTable` | **no** | n/a | `enter` → `action_select_cursor` |

`OptionList.BINDINGS`, verbatim:

```python
Binding("down", "cursor_down", "Down", show=False),
Binding("end", "last", "Last", show=False),
Binding("enter", "select", "Select", show=False),
Binding("home", "first", "First", show=False),
Binding("pagedown", "page_down", "Page Down", show=False),
Binding("pageup", "page_up", "Page Up", show=False),
Binding("up", "cursor_up", "Up", show=False),
```

`DataTable.BINDINGS` adds `left`/`right` for cell cursors, `ctrl+home`/`ctrl+end`
for top and bottom and `home`/`end` for the leftmost and rightmost column. Every
binding in both widgets is `show=False`, so neither contributes anything to the
`Footer` unless the app declares its own.

`OptionList` exposes `enable_option`/`disable_option` (and index and id
variants) which route to `_set_option_disabled`.

### Returning a value from the app

`App` is `Generic[ReturnType]`, and the value travels through `exit`:

```python
def exit(
    self,
    result: ReturnType | None = None,
    return_code: int = 0,
    message: RenderableType | None = None,
) -> None:
    """Exit the app, and return the supplied result.

    Args:
        result: Return value.
        return_code: The return code. Use non-zero values for error codes.
        message: Optional message to display on exit.
    """
```

It sets `_return_value` and `_return_code`, posts `messages.ExitApp()` and
appends the message to `_exit_renderables`. `App.run()` returns
`app.return_value`, typed `ReturnType | None`; `App.return_value` is also a
property. Under `--debug`/`DEBUG`, `app.py` prints the return value with
`Pretty(self._return_value)` at teardown.

So a Textual app hands a caller one typed value and one exit code, and the
message it prints on the way out is a separate argument from the value.

### The testing API

`App.run_test` is an async context manager yielding a `Pilot[ReturnType]`:

```python
async def run_test(
    self,
    *,
    headless: bool = True,
    size: tuple[int, int] | None = (80, 24),
    tooltips: bool = False,
    notifications: bool = False,
    message_hook: Callable[[Message], None] | None = None,
) -> AsyncGenerator[Pilot[ReturnType], None]:
```

Its docstring gives the shape:

```python
async with app.run_test() as pilot:
    await pilot.click("#Button.ok")
    assert ...
```

`Pilot` (`src/textual/pilot.py`) offers `press(*keys)`, `click(...)`,
`hover(...)`, `resize_terminal(width, height)`, `pause(delay=None)`,
`wait_for_animation()`, `wait_for_scheduled_animations()` and `exit(result)`.
Tooltips and notifications are off unless asked for, and the terminal is a fixed
80×24 unless `size` says otherwise. `docs/guide/testing.md` names `pause()` as
the fix for a test that races the message pump: "You can generally solve this by
calling `pause()` which will wait for all pending messages to be processed."

The same guide points at snapshot testing as a separate, optional layer:
"Textual uses snapshot testing internally to ensure that the builtin widgets look
and function correctly in every release", via the plugin
`pytest-textual-snapshot`, whose snapshots "always fail on the first run".

### Style guide and app-design guidance

There is none, in the sense of a document saying what keys an app should bind or
how it should be laid out. `docs/guide/design.md` is titled *Themes* and is
entirely about colour variables. `docs/how-to/design-a-layout.md` is about
layout mechanics and opens with "Tip 1. Make a sketch". The rest of `docs/guide/`
is CSS, actions, animation, app, command palette, content, devtools, events,
input, layout, queries, reactivity, screens, styles, testing, widgets and
workers. No interaction conventions are prescribed anywhere.

### The devtools

`textual console` and the `--dev` mode connect over a socket rather than adding
keys: `App.__init__` constructs a `DevtoolsClient(constants.DEVTOOLS_HOST)` only
when `"devtools" in self.features`, and installs a `StdoutRedirector` so `print`
reaches the console. `App.log` writes to it when connected. No default key
binding is added for the devtools, and none was found in `app.py`.

## 6. Prior art for the cost report

This is where the survey most changes what can be claimed. The claim tested was
that no local-model tooling already shows, before you commit to a model, whether
it fits available memory, what context window it would be served at, or that
switching costs a load and discards a cached prefix. Taken as three claims, one
is **falsified outright**, one **survives**, and one is **falsified for a
different kind of cache**.

### Does it fit — falsified. Three tools do this already.

**Jan is the closest thing found, and it is close.** Since v0.8.0, released
2026-05-22, its changelog says:

> The Hub and provider model lists now show a colored fit pill — **Fits**, **May
> be slow**, or **Won't fit** — based on your hardware, without downloading
> anything.

and the manual repeats it with the wording of the tiers. The implementation is
`web-app/src/lib/modelCompatibility.ts`, and it is not a stub. `estimateModelFit`
takes the weights in bytes, a context length and the machine, and:

- adds a KV-cache estimate, `fileSizeBytes * 0.1 * (ctx / 4096)` —
  `estimateKvCacheBytes`, keyed on `KV_HEURISTIC_RATIO` and `KV_BASELINE_CTX`;
- branches on Apple Silicon specifically. `isAppleSilicon` is
  `os_type === 'macos' && cpu.arch === 'aarch64' && gpus.length === 0`, and that
  branch computes usable memory as total minus a fixed
  `APPLE_SILICON_FIXED_OVERHEAD` of 2.5 GiB minus a variable ten per cent, then
  returns green below 85 per cent of usable (`APPLE_SILICON_COMFORTABLE_RATIO`),
  yellow above it, red past usable;
- falls back to a VRAM-versus-RAM split with a `DISCRETE_RESERVE_BYTES` of about
  2.13 GiB on machines that have a discrete GPU.

That is: weights plus a window-scaled cache, against the memory a Mac can
actually give, with three verdicts and a fourth for "could not estimate". The
shape of the calculation is the same shape.

Two bounds on how close it is. In the Hub — the download list, where the pill
appears per row — the caller is `ModelInfoHoverCard`, which passes the constant
`DEFAULT_CTX_LENGTH = 8192` rather than any window the model would be served at.
Only `ModelSupportStatus` takes a real one, and its single caller
`DropdownModelProvider` passes `getContextSize()`, which reads
`selectedModel.settings.ctx_len.controller_props.value` and returns 8192 when
unset — and it renders inside the picker's `PopoverTrigger`, that is, next to the
model already selected, not on the rows being browsed.

**GPT4All has had a fit warning since long before that**, though it is dormant:
a `RAM required` column on every row and, where `LLM.systemTotalRAMInGB() <
ramrequired`, the banner quoted in section 3. It compares against total system
RAM, not against a GPU share, and `ramrequired` is a number published in the
model catalogue rather than computed. Nothing in it depends on the window.

**LM Studio prices a load from the command line.** `lms load --estimate-only`
was added in 0.3.27, 2025-09-24, and the changelog describes it as printing
"estimated GPU and total memory before loading. Honors `--context-length` and
`--gpu`, and uses an improved estimator that now accounts for flash attention
and vision models." The docs repeat it: "Optional flags such as
`--context-length` and `--gpu` are honored and reflected in the estimate. The
estimator accounts for factors like context length, flash attention, and whether
the model is vision-enabled."

Run on this machine on 2026-08-26, it prints:

```
$ lms load qwen/qwen3.6-35b-a3b --estimate-only

Model: qwen/qwen3.6-35b-a3b
Estimated GPU Memory:   26.64 GiB
Estimated Total Memory: 26.64 GiB
Confidence: LOW

Estimate: This model may be loaded based on your resource guardrails settings.
```

**Measured, 2026-08-26: the context length does not reach the estimate.** Three
models were each estimated at two windows 128 times apart, and every pair is
byte-identical:

```
qwen/qwen3.6-35b-a3b   -c 2048   → 26.64 GiB      -c 262144 → 26.64 GiB
google/gemma-4-e4b     -c 2048   →  8.95 GiB      -c 262144 →  8.95 GiB
lfm2.5-1.2b-instruct   -c 2048   →  1.63 GiB      -c 262144 →  1.63 GiB
```

A fourth model, `qwen/qwen3.6-27b`, gave 20.97 GiB at both 4,096 and 131,072,
and echoed the requested `Context Length` back above an unchanged figure. This
contradicts the documentation, and it matches what `docs/research/adapter-surfaces.md`
already measured for the other flag the docs say is honoured — `--gpu off` and
`--gpu max` returning the same number to the hundredth. Every model on this
machine is MLX, so the finding is bounded to that path; whether the GGUF path
differs was not tested. The three other verdict strings the estimator can print
could not be established: no local model exceeds this machine, and the `lms`
binary is a compiled bundle in which the one known verdict string does not
appear as plain text, so the set could not be enumerated by reading it.

**What does not do this.** Ollama's desktop model picker
(`app/ui/app/src/components/ModelPicker.tsx`) shows names and a search box, and
nothing about memory. Ollama does compute a prediction internally —
`llm.PredictServerVRAM` is called from `server/sched.go`, which logs "llama-server
model predicted to exceed available memory, evicting" and "model is too large for
system memory" — but that is the scheduler's, at load time, in a log, and it is
not surfaced anywhere a person chooses from. llama-swap's web UI lists models
with a load/unload button per row (`ui/src/components/ModelLoadButton.svelte`,
whose `title` is `Unload`, `Cancel` or `Load` by state) and shows no memory
figure at all. Cline shows a context window and a price, both properties of the
model and the vendor rather than of the machine. oMLX and LocalAI were not
examined for this question.

### What window it would be served at — not falsified

Nothing found shows, before you commit, the window a model *would be served at*
as against the window it *could* be served at. Every figure in the survey is one
of two other things.

It is either the ceiling — the model's own maximum. Cline's `ModelInfoView`
renders `contextWindow` compactly, `"200K"` in its own example. GPT4All's
context-length field is bounded by `maxContextLength` and its help text is
"Number of input and output tokens the model sees.", with nothing said about
what it costs. Claude Code's model aliases document `sonnet[1m]` and `opus[1m]`
as selecting "a 1 million token context window", again a maximum.

Or it is a window *asked for*: `lms load -c`, `llama-server --ctx-size`, Ollama's
`OLLAMA_CONTEXT_LENGTH`, Jan's `ctx_len` setting. In no case does a surface show
what came back.

The one place a served window is reported at all is *after* the model is
resident. `ollama ps` prints a `CONTEXT` column — `cmd/cmd.go`,
`ListRunningHandler`, `ctxStr := strconv.Itoa(m.ContextLength)` — alongside
`SIZE`, a `PROCESSOR` column computed from `SizeVRAM` against `Size` as
`100% CPU`, `100% GPU`, `Unknown` or `"%d%%/%d%% CPU/GPU"`, and an `UNTIL`
column. That is a report of what is being served now, on a model already loaded,
which is the position offgrid's `doctor` already occupies.

### Switching costs a discarded prefix — falsified, for a remote cache

Claude Code does exactly this, and asks before it does it.

From
[`code.claude.com/docs/en/prompt-caching`](https://code.claude.com/docs/en/prompt-caching),
the *Switching models* section:

> Each model has its own cache. Switching with `/model` means the next request
> reads the entire conversation history with no cache hits, even though the
> content is identical.
>
> When you run `/model` at the terminal, Claude Code asks you to confirm the
> switch only while the cache is still warm. The cache stays warm for one cache
> TTL after Claude Code last sent a request in this conversation or Claude last
> responded. Once that time passes, the cache has expired, so Claude Code
> switches without asking.
>
> Before v2.1.238, Claude Code didn't check the cache TTL and asked even after
> the cache had expired.

The same page frames the whole subject in the terms the question uses — "Most of
them are avoidable mid-task once you know they have a cost. A model switch can
feel free until you notice the slower turn that follows." — and lists eight
actions that invalidate the cache, of which switching models, changing effort
level and turning on fast mode are all keyed to the request rather than to
content. Changing effort "follows the same confirmation as switching models".

Three things bound the analogy. The cache is server-side, in "whichever
infrastructure serves your model", and what it costs is a slower and more
expensive turn rather than a load. The confirmation is conditional on the cache
being warm, which Claude Code knows from a TTL it controls. And the model being
switched to is remote, so nothing is being made resident and nothing is being
let go of.

No local-model tool in the survey warns that switching costs a load.
llama-swap's entire purpose is swapping models under a proxy — its config has a
`stop-timeout` and its UI has per-model load and unload buttons — and it says
nothing about what a swap costs. LM Studio documents its TTL and Auto-Evict
behaviour in prose but has no surface that says "this choice costs a load".
Ollama's `keep_alive` is a knob, not a warning.

### The claim, restated against what was found

- **Fit against this machine's memory, shown before committing**: not novel.
  Jan does it per row with a window-scaled cache estimate and an Apple Silicon
  branch; GPT4All does it per row from a published figure; LM Studio does it on
  demand from the command line, though not — measured here — as a function of the
  window, whatever its documentation says.
- **The window a model would be served at, shown before committing**: not found
  anywhere. Every figure surveyed is either the ceiling or the window asked for,
  and the one served-window report in the survey, `ollama ps`, is for a model
  already resident.
- **Switching costs a load and discards a cached prefix, said before
  committing**: found, once, in Claude Code, about a server-side prompt cache
  and a remote model. Not found in any tool that holds a model on the machine
  it runs on.

The three together, on one surface, were not found. Each individually was
looked for hard, and two of the three turned up.

## What could not be established

- **The keymap of `lms load`'s interactive picker.** Driving it would have
  loaded a model, and it takes no flag to preview the picker without acting.
- **The other verdicts `lms load --estimate-only` can print.** No local model
  exceeds this machine, and `strings` over the `lms` binary does not find the
  one verdict string that was seen, so the compiled bundle cannot be used to
  enumerate the rest. `docs/research/adapter-surfaces.md` records that reading a
  compiled bundle has produced false "measured" claims before, and no claim here
  rests on one.
- **Whether LM Studio's estimator honours `--context-length` on the GGUF path.**
  Every text model on this machine is MLX. The measurement above bounds the
  finding to MLX.
- **Claude Code's picker beyond what its documentation states.** It is closed
  source, and the two published keys, the row labels and the switch confirmation
  are the whole of what could be read.
- **What Claude Code's model-switch confirmation literally says.** The docs
  state that it asks and when; they do not quote the prompt, and no session was
  driven to produce one.
- **Ollama's `ps` output on this machine.** No Ollama models are installed here,
  so the command printed no rows; the columns above are from `cmd/cmd.go`.
- **oMLX, LocalAI and Hugging Face's own hub indicators** for question 6. Time
  ran out; each is a live candidate for falsifying the fit half of the claim
  further, though the half is already falsified.
