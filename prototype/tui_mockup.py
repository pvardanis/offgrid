# ruff: noqa
"""Throwaway visual mockup of the redesigned offgrid picker — Q4 layout.

Not wired to the domain, no network, all data is faked. Its only job is to let
Danny see the settled shape before it is built for real:

  - persistent header band: ASCII banner + version (git SHA) + cwd
  - left column: runtime / agent dropdowns + models list (as today)
  - right column, two stacked panels:
      * "This machine" — what fits + a Recommend button that reveals a ranked
        DataTable in place (no modal, same screen)
      * "This run" — trimmed signal rows (colour-coded), conversations path a
        first-class row, and a `d`-toggled Collapsible holding the debug dump
  - footer: s / q / r / d ; status line carries `enter`
  - nord theme

Run:  uv run python .scratch/tui_mockup.py
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Footer,
    Label,
    OptionList,
    Select,
    Static,
)

BANNER_ROWS = (
    "█▀█ █▀▀ █▀▀ █▀▀ █▀▄ █ █▀▄",
    "█ █ █▀▀ █▀▀ █▄█ █▀▄ █ █ █",
    "▀▀▀ ▀   ▀   ▀▀▀ ▀ ▀ ▀ ▀▀▀",
)

# Banner is fixed emboss and the button fixed link — the only live control the
# shipped screen keeps is the theme cycle below.
BUTTON_LABEL_OPEN = "[ ▸ recommend models ]"
BUTTON_LABEL_SHOWN = "[ ▾ recommend models ]"

# `t` cycles these live; the chosen one persists in the profile. Default first.
THEMES = [
    "catppuccin-mocha",
    "nord",
    "tokyo-night",
    "gruvbox",
    "dracula",
    "monokai",
    "flexoki",
    "textual-dark",
]

VERSION = "offgrid @ 3ae7a9a"
CWD = "~/Documents/projects/offgrid  ·  the dir the agent inherits"

FITS = """\
Apple M2 Max · 64GB unified memory · GPU limit 48GB · usable 48GB

A model of about this size fits, leaving room for context:

   4-bit    70B parameters
   8-bit    35B parameters
  16-bit    17B parameters"""

# Faked ranked shortlist: model · params (active if MoE) · quant · quality · context
RECOMMENDATIONS = [
    ("qwen3-coder-30b-a3b", "30B (3B active)", "4-bit", "excellent · 84", "262144"),
    ("glm-4.6-32b", "32B", "4-bit", "excellent · 81", "200000"),
    ("qwen3-coder-30b-a3b", "30B (3B active)", "8-bit", "strong · 76", "262144"),
    ("devstral-24b", "24B", "4-bit", "strong · 72", "131072"),
    ("gpt-oss-20b", "20B", "8-bit", "fair · 63", "131072"),
]

RECOMMEND_CAPTION = (
    "onyx · swe_bench_verified · read today · "
    "dropped 3: no params (1), no score (1), too large (1)"
)


class Mockup(App[None]):
    """Static picker mockup — nord, header band, two-panel right side."""

    CSS = """
    #header {
        height: auto;
        padding: 0 1;
        border-bottom: solid $panel;
    }
    #header-row { height: auto; }
    #banner { text-style: bold; height: auto; width: auto; }
    #banner > Static { height: 1; width: auto; }
    #banner > #banner-1 { color: $accent-lighten-2; }
    #banner > #banner-2 { color: $accent; }
    #banner > #banner-3 { color: $accent-darken-2; }
    #meta { color: $text-muted; height: auto; width: 1fr; padding: 0 0 0 3; }
    #meta-version { color: $accent; text-style: bold; height: 1; }
    #meta-cwd { color: $text-muted; height: 1; }
    #theme-name { color: $text-muted; height: 1; }

    #lists { width: 44; }
    .box {
        border: round $panel;
        background: $surface;
        border-title-color: $text;
        border-title-style: bold;
        border-title-align: left;
    }
    .box:focus-within { border: round $accent; border-title-color: $accent; }
    .box.pick { height: auto; }
    .box.pick > Select { border: none; background: $surface; }
    #model-box { height: 1fr; }
    #model-box > OptionList { height: 1fr; border: none; background: $surface; }

    #right { width: 1fr; }
    #machine-box { height: 1fr; }
    #run-box { height: 1fr; }

    #fits { padding: 0 1; height: auto; }

    /* Link-style button: no fill, no border, padding zero so nothing clips the
       brackets. Container sizes to its widest child and centres both, so the
       hint sits centred under the button. */
    #rec-cta { width: auto; height: auto; align-horizontal: center; margin: 1 0 0 0; }
    #rec-btn.link {
        width: auto;
        height: 1;
        min-width: 0;
        padding: 0;
        border: none;
        background: transparent;
        color: $accent;
        text-style: bold;
    }
    #rec-btn.link:hover { color: $accent-lighten-1; }
    #rec-hint {
        color: $text-muted;
        height: 1;
        width: auto;
        text-align: center;
    }
    #rec-table { height: 10; padding: 0 1; display: none; }
    #rec-caption { color: $text-muted; padding: 0 1; height: auto; display: none; }
    #download-hint { color: $success; padding: 0 1; height: auto; display: none; }

    .signal { padding: 0 1; height: auto; }
    .ok { color: $success; }
    .warn { color: $warning; }
    .bad { color: $error; }
    .dim { color: $text-muted; }

    #status { color: $text-muted; padding: 0 1; height: 1; }
    """

    BINDINGS = [
        Binding("s", "noop", "run once"),
        Binding("q", "quit", "leave"),
        Binding("r", "recommend", "recommend"),
        Binding("d", "noop", "details"),
        Binding("t", "cycle_theme", "theme"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._theme_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="header"), Horizontal(id="header-row"):
            with Vertical(id="banner", classes="emboss"):
                yield Static(BANNER_ROWS[0], id="banner-1")
                yield Static(BANNER_ROWS[1], id="banner-2")
                yield Static(BANNER_ROWS[2], id="banner-3")
            with Vertical(id="meta"):
                yield Static(VERSION, id="meta-version")
                yield Static(CWD, id="meta-cwd")
                yield Static("", id="theme-name")

        with Horizontal():
            with Vertical(id="lists"):
                with Vertical(id="runtime-box", classes="box pick"):
                    yield Select(
                        [("lmstudio", "lmstudio")],
                        value="lmstudio",
                        allow_blank=False,
                        compact=True,
                    )
                with Vertical(id="agent-box", classes="box pick"):
                    yield Select(
                        [("claude-code", "claude-code"), ("opencode", "opencode")],
                        value="claude-code",
                        allow_blank=False,
                        compact=True,
                    )
                with Vertical(id="model-box", classes="box"):
                    yield Static(
                        "model                      held  context", classes="dim"
                    )
                    ol = OptionList(
                        "qwen3-coder-30b-a3b     ✅   262144",
                        "glm-4.6-32b                  200000",
                        "devstral-24b                 131072",
                    )
                    yield ol

            with Vertical(id="right"):
                with Vertical(id="machine-box", classes="box"):
                    yield Static(FITS, id="fits")
                    with Center(), Vertical(id="rec-cta"):
                        yield Button(BUTTON_LABEL_OPEN, id="rec-btn", classes="link")
                        yield Static("ranked for this machine", id="rec-hint")
                    yield DataTable(id="rec-table")
                    yield Static(RECOMMEND_CAPTION, id="rec-caption")
                    yield Static("", id="download-hint")

                with Vertical(id="run-box", classes="box"):
                    yield Label(
                        "qwen3-coder-30b-a3b is held, so this costs no load",
                        classes="signal ok",
                    )
                    yield Label("served at 262144 (ceiling 262144)", classes="signal")
                    yield Label(
                        "claude-code · pair can talk (anthropic)", classes="signal"
                    )
                    yield Label(
                        "conversations → ~/.offgrid/claude-code/  (offgrid's own; "
                        "resume with offgrid run -- --resume)",
                        classes="signal",
                    )
                    with Collapsible(title="details", collapsed=True):
                        yield Static(
                            "runtime   lmstudio at 127.0.0.1:1234, serves anthropic + openai\n"
                            "request   model qwen3-coder-30b-a3b, no window (inherit served)\n"
                            "agent     context floor 16000\n"
                            "discarded no window this runtime refused\n"
                            "dialect   agent speaks anthropic ∈ {anthropic, openai}",
                            classes="dim",
                        )

        yield Static(
            "enter runs and saves · s runs once · this is your saved profile",
            id="status",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()
        self.query_one("#runtime-box", Vertical).border_title = "runtime"
        self.query_one("#agent-box", Vertical).border_title = "agent"
        self.query_one("#model-box", Vertical).border_title = "models"
        self.query_one("#machine-box", Vertical).border_title = "this machine"
        self.query_one("#run-box", Vertical).border_title = "this run"

        table = self.query_one("#rec-table", DataTable)
        table.add_columns("model", "params", "quant", "quality", "context")
        for row in RECOMMENDATIONS:
            table.add_row(*row)
        table.cursor_type = "row"

    def action_recommend(self) -> None:
        self._toggle_recommendations()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._toggle_recommendations()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # A click moves the cursor and highlights, so highlight (not select)
        # covers click, arrows and enter alike. Per-runtime download
        # instructions — in the real build this is
        # describe_model_download(runtime_name, model), handed in.
        table = self.query_one("#rec-table", DataTable)

        if not table.display:
            return

        model = RECOMMENDATIONS[event.cursor_row][0]
        hint = self.query_one("#download-hint", Static)
        hint.update(f"to download {model} into lmstudio:\n  lms get {model}")
        hint.display = True

    def _toggle_recommendations(self) -> None:
        table = self.query_one("#rec-table", DataTable)
        caption = self.query_one("#rec-caption", Static)
        button = self.query_one("#rec-btn", Button)
        showing = table.display

        # Reveal below the summary, fits stays full; only the arrow flips, so
        # the label keeps one width and the hint under it stays aligned.
        table.display = not showing
        caption.display = not showing
        if showing:
            self.query_one("#download-hint", Static).display = False
        button.label = BUTTON_LABEL_OPEN if showing else BUTTON_LABEL_SHOWN

    def action_cycle_theme(self) -> None:
        self._theme_index = (self._theme_index + 1) % len(THEMES)
        self._apply_theme()

    def _apply_theme(self) -> None:
        name = THEMES[self._theme_index]
        self.theme = name
        self.query_one("#theme-name", Static).update(f"theme: {name}  ·  t to cycle")

    def action_noop(self) -> None:
        pass


if __name__ == "__main__":
    Mockup().run()
