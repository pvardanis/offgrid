# Picker redesign prototype

Throwaway prototype that settled the look of the picker redesign — static data,
no network, no domain wiring. Kept as a primary source for the implementation.

Run:

    uv run python prototype/tui_mockup.py

Keys: `r` reveal the recommend table · click/arrow a row for download
instructions · `d` details · `t` cycle theme · `q` quit.

Shows: catppuccin-mocha default, 3-row emboss block banner, link-style recommend
button, 50/50 right column (this-machine over this-run).

Spec: pvardanis/offgrid#214. Tickets: #215 (header), #216 (panels), #218
(theme), #219 (recommend), #220 (download).
