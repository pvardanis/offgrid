"""Where the screen's widgets sit, and the ids they answer to.

The picker is a behaviour: it reads once the screen is up, routes the keys, and
recomputes the report as a pick moves. What each widget is called and how the
shell lays them out is the frame that behaviour runs inside, kept here so the
class reads as what it does rather than as a wall of layout. The ids are what
`compose` builds against and what the CSS styles, so they live beside the CSS
that uses them.
"""

REPORT = "report"
"""Where the report is shown, which is what a test reads it back from."""

PANE = "pane"
"""What the report scrolls inside, since it is as long as the machine makes it."""

RIGHT = "right"
"""The column beside the lists, split into the machine panel over the run one."""

MACHINE = "machine"
"""The upper right panel: what this machine holds, at each quantization width."""

FITS = "fits"
"""Where the machine panel says what fits, which a test reads it back from."""

RUN = "run"
"""The lower right panel: what the highlighted pairing would do."""

SIGNAL = "signal"
"""Where the run panel's few colour-coded lines are, read back by a test."""

SIGNAL_PANE = "signal-pane"
"""What the signal scrolls inside, so its share of the run panel is bounded.

The signal takes half the run panel and the detail the other half; a share
that is a fraction of the panel is bounded rather than as tall as the lines
make it, so on a short terminal the signal scrolls to its end rather than
pushing the detail off.
"""

DETAIL = "detail"
"""The collapsible the curated detail waits behind, closed by default."""

LISTS = "lists"
"""What the two dropdowns and the models list are stacked in."""

RUNTIME_BOX = "runtime-box"
"""The titled box the runtime dropdown sits in."""

AGENT_BOX = "agent-box"
"""The titled box the agent dropdown sits in."""

MODEL_BOX = "model-box"
"""What the models list and the names of its columns share a border with."""

COLUMNS = "columns"
"""Where the names of the model list's columns are shown.

Above the list rather than a row in it, so that it stays where it is when a
machine with a shelf full of models scrolls.
"""

STATUS = "status"
"""Where it is said which key writes, and whether a run would change anything.

A line of its own above the footer's key hints. `enter` runs both a `Select`
and an `OptionList` themselves before the app is reached, so Textual's `Footer`
never shows its hint while either has the focus — which is always here. Which
key writes is said here instead, beside the one fact the footer could not carry
anyway: whether what is assembled is still what the file holds, which is
rewritten as the highlight moves.
"""

RUNTIMES = "runtimes"
AGENTS = "agents"
MODELS = "models"

SHELL_CSS = f"""
/* A layer above the lists for the window slider to float on, so it draws
   over the row it edits rather than pushing the list about. */
Screen {{
    layers: base overlay;
}}

#{LISTS} {{
    width: 44;
}}

.box {{
    border: round $panel;
    /* On the box rather than on the widget inside it, so that a heading and
       what it is over are one surface: a heading left transparent paints
       the screen behind it and reads as a second box. */
    background: $surface;
    /* A title drawn in the border colour is as faint as the border, and
       these three are what say which box a person is looking at. */
    border-title-color: $text;
    border-title-style: bold;
    border-title-align: left;
}}

/* Which box has the keys is worth seeing, with three of them on screen and
   every one of them answering to the same arrows. */
.box:focus-within {{
    border: round $accent;
    border-title-color: $accent;
}}

/* The dropdowns are as tall as their one line; the models list takes the
   rest. */
.box.pick {{
    height: auto;
}}

.box.pick > Select {{
    border: none;
    background: $surface;
}}

#{MODEL_BOX} {{
    height: 1fr;
}}

#{MODEL_BOX} > OptionList {{
    height: 1fr;
    border: none;
    background: $surface;
}}

#{COLUMNS} {{
    color: $text-muted;
    padding: 0 1;
}}

#{RIGHT} {{
    width: 1fr;
}}

/* The two panels split the column evenly: what this machine holds, over
   what the highlighted run would do. */
#{MACHINE}, #{RUN} {{
    height: 1fr;
}}

#{FITS} {{
    padding: 0 1;
}}

#{SIGNAL} {{
    padding: 0 1;
}}

/* The signal and the detail split the run panel evenly, a half each. Each
   scrolls within its half on a terminal too short to hold it whole. */
#{SIGNAL_PANE} {{
    height: 1fr;
}}

#{DETAIL} {{
    height: 1fr;
}}

/* The curated detail scrolls inside the collapsible, so a summary taller
   than its share is still read to the end once the detail is opened. */
#{DETAIL} #{PANE} {{
    height: 1fr;
}}

#{STATUS} {{
    color: $text-muted;
    padding: 0 1;
    height: 1;
}}
"""
