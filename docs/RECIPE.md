# Eartag

A side panel, next to Files and Changes, about the agent you focus. It tells you at a glance what the conversation is about, what you last asked,
what the agent did and whether it is done, plus context and quotas left; a second tab lists the tab's scratch pad
scratch pad, as a real nvim filling the panel.

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
- **Pad**: the panel shrinks to its tab bar (31px) and a real nvim on the tab's scratch pad fills the rest,
  running on the agent's machine. Messages only when there is no nvim to show (pad being created, failure,
  agent on another machine).

## How it behaves

- Alt+I (`eartag-key.toggle`): `layout.select {stack: "panel-body", child: "eartag"}` + `layout.show {id: "panel"}`,
  or `layout.hide {id: "panel"}` when Eartag already shows. The panel shows the focused agent; focusing a shell or
  the pad's nvim keeps the agent last focused in that tab; a tab never focused shows its first agent.
- Status is live from `agents()`. The document is fetched every 3 s while the agent works or right after its status
  changes, else every 15 s, and only while the panel shows.
- Pad tab: one nvim per box, a herdr-core terminal named `eartag-pad`
  (`hc run --on <machine> --name eartag-pad --bg --no-parent -- nvim --listen <socket> <pad>`, argv and socket from
  the JSON). The layout shows it by name in a fixed block; Pad does `layout.show {id: "eartag-pad"}` +
  `layout.resize {id: "eartag-view", px: 31}`, Recap the reverse. Another agent's pad: `nvim --server <socket>
  --remote-send "<C-\><C-N>:update | edit <pad><CR>"`. Checked every 10 s; an nvim that exited is started again. A tab without a pad gets one the first time its Pad tab
  shows: `eartag.py pad-start --terminal tN` = `HC_TERMINAL_ID=tN scratch --set-session <agent session>` (what the
  SessionStart hook does: line 1 binds the pad to that session; no pane opens), once per agent; failures are shown.
- Box unreachable / eartag failing: a quiet message, or the last document flagged "stale". Never a crash.

## Built from

- Layout: the `eartag` column in the `panel-body` stack of the right `panel` column, beside `files` and
  `changes`: `eartag-view` (mod `eartag`) and `eartag-pad` (`hidden: true`, `{terminal: "personal-agent-env/eartag-pad"}`).
- `mods/eartag` (`place: none`): `main.js` (view, polling, focus), `layout.js` (pure: which agent, the nvim block
  edit), `data.js` (`exec("python3", ["proj/herdr-eartag/eartag.py", "json", "--terminal", tN], {on: machine})`),
  `nvim.js`, `recap.js`, `padtab.js`, `style.js`.
- `mods/eartag-key` (`place: none`, a 1px block in the layout, draws nothing): receives `eartag-key.toggle`, decides
  with `toggle.js` (pure). Adds `eartag` to `shared("workspace.panels")`, or the tab bar closes it on a space switch.
- Box side: `eartag.py json` = `PanelModel` with `source.CoreSource` (`hc get tN --json` +
  `~/.claude/sessions/<pid>.json`; pad from `HC_TERMINAL_ID=tN SCRATCH_GUARD=off scratch --path`), serialized by
  `payload.py`.

## Watch out

- The mod runtime has no `structuredClone` (node has, so tests pass): copy trees with a JSON round trip.
- The app drops a terminal block from the layout file when its terminal ends; the panel puts it back with a
  direct file edit (`readTextFile` + `writeTextFile` of `layouts/<shown>.json`), which keeps the clicks.
- Never `layout.set` at run time: it replaces the file and wipes the layout's clicks (`layouts/.state`), sizes and
  shown panels included. Show, hide and resize only; the nvim block names a terminal, so it never changes.
- A mod's props come from `props()`, not from `init`'s first argument.
- `hc send` pastes and presses Enter: never use it to drive nvim; use its `--listen` socket.
- `herdr-app shot` can return a frame minutes old: don't trust it to confirm a change.
- `exec` on the box may lack `~/.local/bin` (hc) and `~/.bin` (scratch) on PATH; `eartag.py` adds them itself.
- Verdict chips come from rephrasing (`summarize` in the eartag config). With it off you get status and "your turn"
  only, as in the TUI. `json` never waits for rephrasing: a detached child fills the cache for the next run.

## Done when

- `python3 eartag.py json --terminal t2` on the box prints the document in well under a second.
- Alt+I shows the panel with the focused agent, Alt+I hides it; focusing an agent in another tab switches it.
- Status and verdict change while the agent works; on Pad, nvim on the agent's pad fills the panel; another agent's Pad shows its pad.
- `herdr-app check` passes for both mods; `node --test app/tests/` and the Python tests pass.
