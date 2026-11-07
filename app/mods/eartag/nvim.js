// The Pad tab is a real nvim on the pad: one per machine, a herdr-core terminal named
// `eartag-pad` (pad.nvim.name). The layout shows it by name in a fixed block (layout.js), so
// switching agents never edits the layout: the same nvim `:edit`s the other agent's pad,
// through its `--listen` socket (never by typing keys into it).

import { exec, hc } from "herdr";

/** Is the named nvim live on `machine`? */
async function live(machine, name) {
  try {
    const r = await hc(["get", `${machine}/${name}`, "--json"]);
    return r.code === 0 && JSON.parse(r.stdout).state === "live";
  } catch (_e) {
    return false;
  }
}

/** Keys for the running nvim; quiet when it is gone. */
async function send(machine, pad, keys) {
  try {
    const r = await exec("nvim", ["--server", pad.nvim.socket, "--remote-send", keys], { on: machine });
    return r.code === 0;
  } catch (_e) {
    return false;
  }
}

/** Does the nvim answer on its socket? */
async function answers(machine, pad) {
  try {
    const r = await exec("nvim", ["--server", pad.nvim.socket, "--remote-expr", "1"], { on: machine });
    return r.code === 0 && r.stdout.trim() === "1";
  } catch (_e) {
    return false;
  }
}

/** Start it on this pad. A stale socket from a killed nvim would stop --listen: drop it first. */
async function start(machine, pad) {
  try {
    await exec("rm", ["-f", pad.nvim.socket], { on: machine });
    const args = ["run", "--on", machine, "--name", pad.nvim.name, "--bg", "--json", "--no-parent", "--label", "eartag.pad=1", "--", ...pad.nvim.argv];
    return (await hc(args)).code === 0;
  } catch (_e) {
    return false;
  }
}

/** End the named nvim (it is ours: label eartag.pad=1). */
async function stop(machine, name) {
  try {
    await hc(["kill", `${machine}/${name}`]);
  } catch (_e) {
    // already gone
  }
}

/** The named nvim shows `pad` on `machine`: started, or told to open it (EartagOpen saves
 *  the pad it had open first and wipes it, so buffers never pile up). An nvim that is live
 *  but does not answer on its socket (after a reconnect, say) is replaced by a fresh one.
 *  `current` is the path it showed last. Resolves with an error or null. */
export async function showPad(machine, pad, current) {
  const name = pad.nvim.name;
  if (!(await live(machine, name))) return (await start(machine, pad)) ? null : "nvim did not start on the box";
  if (current === pad.path && (await answers(machine, pad))) return null;
  // EartagOpen (pad_app.lua): save, open, wipe the other buffers.
  const keys = `<C-\\><C-N><Cmd>lua EartagOpen([[${pad.path}]])<CR>`;
  if (await send(machine, pad, keys)) return null;
  await stop(machine, name);
  return (await start(machine, pad)) ? null : "nvim did not answer and could not be restarted";
}
