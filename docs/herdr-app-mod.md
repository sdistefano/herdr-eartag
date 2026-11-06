# Brief: Eartag (with pad) as a Herdr app mod

For the agent on Silvio's laptop, where the Herdr app runs. Written 2026-11-06 on the box (`agent@` the server whose herdr-core
runs the agents). Read all of it before writing code.

## Goal

In the Herdr app (herdr.dev, `herdrdev/herdr-app`, GPUI + JavaScript mods), **Alt+I** toggles a panel on the right of the
focused agent pane, as Ctrl+A i does in the herdr TUI with this repo's Eartag plugin. The panel shows the same as the TUI's:

- **Recap tab**: header (project, permission mode, agent state), last ask with verdict (`✓ DONE`, `◐ PARTIAL`, `✗ FAILED`,
  `? YOUR TURN`, `◐ WORKING`), the tool running now, task progress, three previous asks, files edited with `+/−`, how long the
  ask took, alerts, footer with context used, 5h and 7d quotas, machine, branch, model and effort.
- **Pad tab**: Silvio's extension (commits `b2a751e`, `c7701ca`, `a8033af`). The tab's scratch pad: one line per ` mark
  with its title, the whole line clickable, lit on hover; a click opens the pad in nvim at that mark's line. Checkbox counts.

Screenshots of the TUI version: `docs/hero.png`, `docs/hover.png`, `docs/states.png`.

## The setup (verified on the box, 2026-11-06)

- The Herdr app on the laptop is a client of the **box's herdr-core** (`hc 0.1.18`, socket
  `/run/user/1000/herdr-core/default.sock`). Every agent is a box terminal (`t2`, `t18`, …) with labels `herdr.space`,
  `herdr.tab`, `where`, `agent-status`. From the mod, those spaces have `machine` set to the box's machine name.
- So **all data lives on the box**: Claude transcripts, `~/.claude/sessions/<pid>.json`, the statusline relay cache
  (`~/.local/state/herdr-eartag/`), the git repos, the pads in `/var/scratchpad/`. The mod runs on the laptop and must get it
  with `exec(cmd, args, { on: space.machine })` or `readTextFile(path, { on })`.
- This repo is cloned on the box at `~/proj/herdr-eartag` (origin `git@github.com:sdistefano/herdr-eartag.git`, branch `main`).
  The herdr TUI plugin runs from a herdr-managed checkout of the same fork; leave that alone.

## Design: two halves

### 1. Box side: `eartag.py json --terminal tN` (Python, in this repo)

A new subcommand that prints one JSON document with everything the panel draws. Reuse the existing model; don't fork it:

- `herdr_eartag/panel.py` `PanelModel` builds the view model from a herdr TUI pane (`herdr pane get`). Its inputs are the
  pane's `agent_session` (session id), `cwd`/`foreground_cwd` and `agent`. Under herdr-core there is no `herdr pane get`;
  get the same facts this way (all checked by hand):
  - `hc get tN --json` gives `foreground.pid`, `foreground.cwd`, `foreground.name` (`claude`), `cwd`, `labels`.
  - `~/.claude/sessions/<foreground.pid>.json` gives `sessionId` and `cwd`. Example: t18, pid 3297601 →
    `f3692ac2-5c10-48d3-91f2-97727dc6b5df`.
  - From the session id, the existing `claude.find_transcript`, `claude.read_tasks`, `statusline.read_session` and
    `gitinfo.find` work unchanged.
- Add an input adapter (a small class with the fields `PanelModel` reads), not `if hc: … else: …` branches through the panel.
  Keep `render.py`/`tui.py` (ANSI drawing) out of the JSON path: emit the view model (`v.project`, verdict, asks, files,
  quotas, …) as data. Colours are the mod's job (theme), so send semantic states, not ANSI codes.
- **Pad**: resolve the terminal's pad with `HC_TERMINAL_ID=tN SCRATCH_GUARD=off scratch --path` (prints e.g.
  `/var/scratchpad/hc-gaucho:1.md`; without `SCRATCH_GUARD=off` it refuses because the pad is bound to another session than the
  caller's). Then `pad.parse()` and emit `sections` (letter, title, line, filled), `glossary`, `todo`, `read_now` and the path.
  Read only, as in the TUI: the panel never writes a pad.
- Summaries (rephrasing via `summarize.py`) are slow: never block `json` on them. Return what is cached and let a later call
  pick the rest up.
- Python rules for this box: black after changes, small functions, dispatch dicts over if/else chains, docstrings.
  Tests: add tests for the adapter and the JSON shape (fixtures, no live herdr-core in tests); watch each fail before it passes.

You can work on the box over ssh, or clone the fork on the laptop and push. Commit messages: one line, under 80 chars,
`eartag: <lowercase description>` (no ticket). Push to `main`.

### 2. Laptop side: the mod `~/.config/herdr-app/mods/eartag/`

Read `~/.config/herdr-app/AGENTS.md` (the app rewrites it every start) and the `herdr.d.ts` / `gpui-kit.d.ts` beside it first;
they are the truth for your installed version. What I took from the current upstream guide:

- A mod is `main.js` (class extending `View`) + `mod.json`. Use `{ "place": "none" }`: it appears only where we put it.
- Open as a pane: `run("pane.split", { direction: "right", pane, mod: "eartag", props: { terminal: "<address>" } })`. A mod
  pane splits, zooms, closes and has a header like any pane, and is saved with its tab.
- Data: `cx.timer.every(3000, …)` + `cx.spawn(async (cx) => { const r = await exec("python3",
  ["/home/agent/proj/herdr-eartag/eartag.py", "json", "--terminal", t], { on: machine }); … cx.notify(); })`. `render`
  already re-runs when `agents()` changes (status), so poll only the transcript side, gently: timers keep running while the
  pane is hidden. Use the address without the `<machine>/` prefix on the box.
- Draw with `theme()` colours (`working`, `blocked`, `done`, `idle`, `muted`, `dim`, `accent`) so it follows the theme.
  Spinners with `.frames([...], 90)`, never a timer.
- **Alt+I**: in `keys.json` under `global`, `"alt-i": "eartag.toggle"` reaches shown copies only (`nextCommand()`), so it
  cannot open the first panel. Pick one and say which in the recipe:
  (a) a tiny always-present companion mod (e.g. in a floating block that renders nothing) that receives `eartag.toggle`,
  looks at `panes()` for an eartag pane with `props.terminal == focused().terminal` in the focused tab, and runs
  `pane.close` or `pane.split`; or (b) an object binding to `pane.split` with the mod, plus `alt-i` inside `mod:eartag`
  running `pane.close` for closing. Check first that `alt-i` isn't taken in `keys.json` and doesn't type a character on the
  laptop's keyboard (macOS Option rules in the guide).
- **Pad clicks**: open the pad in nvim at the mark's line on the box, in a split below the panel:
  `run("pane.split", { direction: "down", pane: <eartag pane>, argv: ["nvim", "+<line>", path] })` on the space's
  machine (a split in a box space runs there). Editable, not `-R`: Silvio edits the pad there. When nvim exits the pane closes. A Recap
  ↔ Pad tab bar at the top of the panel replaces the TUI's nvim winbar (`pad_tabbar.lua`).
- `herdr-app check ~/.config/herdr-app/mods/eartag` after every save, and `herdr-app shot` to look at it. Never call it done
  on a passing check alone.

## Done when

1. On the box, `python3 eartag.py json --terminal t2` prints valid JSON with session id, last ask, verdict, files, quotas and
   the pad (`/var/scratchpad/hc-gaucho:1.md` today) in under a second with a warm cache; the tests pass and black is clean.
2. In the app, Alt+I on a Claude agent pane opens the panel on its right; Alt+I again closes it; on a second agent in another
   tab it opens that agent's panel, not the first's.
3. Verdict and status change live while the agent works (try one working and one done agent); a `herdr-app shot` of each
   state goes in `docs/app-*.png`.
4. The Pad tab lists the pad's marks; clicking `s` opens nvim on the box at that heading's line.
5. `docs/RECIPE.md` (the guide's recipe format) and a README section "Herdr app" describe the mod. The mod folder lives in this
   repo (`app/mods/eartag/`) and is copied, not symlinked, to `~/.config/herdr-app/mods/`.

## Watch out

- The guide forbids HTML, CSS, `setTimeout` and Node APIs in mods; `exec` is the only way to the box's data.
- `exec` defaults to a 30 s timeout and rejects on failure: show a quiet "box unreachable" state, never a crash.
- `scratch --path` exits 3 when no pad resolves: the Pad tab then says so and offers nothing to click.
- Don't touch the TUI plugin's behaviour: the herdr TUI keeps using `panel` / `toggle` as today.

## Reporting

Silvio wants progress he can see: commit and push small steps, and when you finish send him the screenshots and what is
left. If you get stuck on a choice that is his (key, layout), ask him; don't guess.
