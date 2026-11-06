# Eartag

A side panel, next to Files and Changes, about the agent you focus. It tells you at a glance what the conversation is about, what you last asked,
what the agent did and whether it is done, plus context and quotas left; a second tab lists the tab's scratch pad
marks above a real nvim on that pad.

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
  Whole row clickable, `hover` background. Under the list (3 shares to its 1): a terminal block with nvim on the
  pad, on the agent's machine; a mark click moves its cursor to that line.

## How it behaves

- Alt+I (`eartag-key.toggle`): `layout.select {stack: "panel-body", child: "eartag"}` + `layout.show {id: "panel"}`,
  or `layout.hide {id: "panel"}` when Eartag already shows. The panel shows the focused agent; focusing a shell or
  the pad's nvim keeps the agent last focused in that tab; a tab never focused shows its first agent.
- Status is live from `agents()`. The document is fetched every 3 s while the agent works or right after its status
  changes, else every 15 s, and only while the panel shows.
- Pad tab: `hc run --on <machine> --bg --no-parent --rm -- nvim --listen <socket> <pad>` (argv and socket come in
  the JSON), then `layout.set` adds `{id: "eartag-pad", content: {terminal}}` under the panel; Recap removes it (nvim
  keeps running for next time). A mark click: `nvim --server <socket> --remote-send "<C-\><C-N>:<line><CR>zt"` on
  that machine. An nvim that exited is started again.
- Box unreachable / eartag failing: a quiet message, or the last document flagged "stale". Never a crash.

## Built from

- Layout: the `eartag` column (`eartag-view` block, mod `eartag`) in the `panel-body` stack of the right `panel`
  column, beside `files` and `changes`.
- `mods/eartag` (`place: none`): `main.js` (view, polling, focus), `layout.js` (pure: which agent, the nvim block
  edit), `data.js` (`exec("python3", ["proj/herdr-eartag/eartag.py", "json", "--terminal", tN], {on: machine})`),
  `nvim.js`, `recap.js`, `padtab.js`, `style.js`.
- `mods/eartag-key` (`place: none`, a 1px block in the layout, draws nothing): receives `eartag-key.toggle`, decides
  with `toggle.js` (pure). Adds `eartag` to `shared("workspace.panels")`, or the tab bar closes it on a space switch.
- Box side: `eartag.py json` = `PanelModel` with `source.CoreSource` (`hc get tN --json` +
  `~/.claude/sessions/<pid>.json`; pad from `HC_TERMINAL_ID=tN SCRATCH_GUARD=off scratch --path`), serialized by
  `payload.py`.

## Watch out

- A mod's props come from `props()`, not from `init`'s first argument.
- `hc send` pastes and presses Enter: never use it to drive nvim; use its `--listen` socket.
- `herdr-app shot` can return a frame minutes old: don't trust it to confirm a change.
- `exec` on the box may lack `~/.local/bin` (hc) and `~/.bin` (scratch) on PATH; `eartag.py` adds them itself.
- Verdict chips come from rephrasing (`summarize` in the eartag config). With it off you get status and "your turn"
  only, as in the TUI. `json` never waits for rephrasing: a detached child fills the cache for the next run.

## Done when

- `python3 eartag.py json --terminal t2` on the box prints the document in well under a second.
- Alt+I shows the panel with the focused agent, Alt+I hides it; focusing an agent in another tab switches it.
- Status and verdict change while the agent works; on Pad, nvim opens under the marks and clicking `` `s `` moves it to that heading.
- `herdr-app check` passes for both mods; `node --test app/tests/` and the Python tests pass.
