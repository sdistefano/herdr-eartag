# Eartag

A pane on the right of an agent pane that tells you at a glance what the conversation is about, what you last asked,
what the agent did and whether it is done, plus context and quotas left; a second tab lists the tab's scratch pad
marks and opens the pad in nvim at the one you click.

![Eartag](app-done.png)

## What you see

- **Tab bar** (30px, bottom border `border`): `Recap` and `Pad N` (N = marks), active one in `foreground` with a 2px
  `accent` underline, others `dim`. A `dim` "stale" on the right when the last refresh failed (tooltip: why).
- **Recap**, scrolling, 12px padding, 14px between blocks:
  - Header: project (14px semibold), permission-mode chip (`bypass` in `blocked`, else `muted`), status chip
    (`WORKING` in `working` with a braille spinner, `NEEDS YOU` `blocked`, `DONE` `done`, `IDLE` `idle`). Chips are
    18px high, 5px radius, the color at 15% alpha behind its text.
  - "Your turn" line when done or blocked.
  - NOW / LAST ASK heading with the ask's age, session title, the ask (13px, wraps), key points, the tool running
    (spinner while working), task progress (done/total + 5px track in `accent`), the reply with its verdict chip
    (`✓ DONE` done, `◐ PARTIAL` working, `✗ FAILED` blocked, `? YOUR TURN` blocked, `◐ WORKING` working).
  - BEFORE: three previous asks, glyph · time · title. FILES: up to 8, heading carries `+added −removed`. Alerts.
  - Footer pinned at the bottom (top border): CTX / 5H / 7D gauges (5px tracks; green, gold from 70%, red from 90%),
    then machine · branch · model · effort with dots (cool, gold, red at max). Hovering a gauge replaces that last
    line with its detail (reset time), so nothing moves.
- **Pad**: pad name + `☐ done/total`, then one row per mark: `` `x `` (18px wide) and its title, colored by role
  (`a` accent bold, `s` working bold when something waits on you, empty sections `dim`), count on the right.
  Whole row clickable, `hover` background.

## How it behaves

- Alt+I (`eartag-key.toggle`) on an agent pane splits the panel to the right (50/50: herdr gives no size for a split);
  again on the agent or inside the panel closes it. Each agent gets its own panel.
- Status is live from `agents()`. The document is fetched every 3 s while the agent works or right after its status
  changes, else every 15 s (timers run while hidden).
- A pad row click: `pane.split {direction: "down", pane: <panel>, argv: ["nvim", "+<line>", <pad>]}`, on the
  agent's machine; editable; closes when nvim exits.
- Box unreachable / eartag failing: a quiet message, or the last document flagged "stale". Never a crash.

## Built from

- `mods/eartag` (`place: none`): `main.js` (view, polling), `data.js` (`exec("python3",
  ["proj/herdr-eartag/eartag.py", "json", "--terminal", tN], {on: machine})`), `recap.js`, `padtab.js`, `style.js`.
  Props: `{ terminal: "<machine>/tN" }`.
- `mods/eartag-key` (`place: none`, a 1px block in the layout, draws nothing): receives `eartag-key.toggle`, decides
  with `toggle.js` (pure), keeps `shared("eartag.panels")` = `{terminal: panel pane id}`.
- Box side: `eartag.py json` = `PanelModel` with `source.CoreSource` (`hc get tN --json` +
  `~/.claude/sessions/<pid>.json`; pad from `HC_TERMINAL_ID=tN SCRATCH_GUARD=off scratch --path`), serialized by
  `payload.py`.

## Watch out

- `panes()` gives no props for mod panes: the registry is how a panel is found again. The pane id of a split on
  another machine can reach `panes()` a moment later; eartag-key retries for 1.5 s.
- A pane mod's props come from `props()`, not from `init`'s first argument.
- `exec` on the box may lack `~/.local/bin` (hc) and `~/.bin` (scratch) on PATH; `eartag.py` adds them itself.
- Verdict chips come from rephrasing (`summarize` in the eartag config). With it off you get status and "your turn"
  only, as in the TUI. `json` never waits for rephrasing: a detached child fills the cache for the next run.

## Done when

- `python3 eartag.py json --terminal t2` on the box prints the document in well under a second.
- Alt+I opens the panel right of the agent, Alt+I closes it; another agent in another tab gets its own.
- Status and verdict change while the agent works; clicking `` `s `` opens nvim at that heading.
- `herdr-app check` passes for both mods; `node --test app/tests/` and the Python tests pass.
