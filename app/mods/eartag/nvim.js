// The Pad tab's real nvim: a herdr-core terminal on the agent's machine (not a tab of its
// own), shown in the layout under the panel. Started with `--listen <socket>` so a mark
// click can move its cursor (`nvim --server <socket> --remote-send`), never by typing keys.

import { exec, hc } from "herdr";
import { splitAddress } from "./layout.js";

/** Start nvim on pad.nvim.argv on `machine`; resolves with its address, or null. */
export async function startNvim(pad, machine) {
  const on = machine ? ["--on", machine] : [];
  const args = ["run", ...on, "--bg", "--json", "--no-parent", "--rm", "--label", "eartag.pad=1", "--", ...pad.nvim.argv];
  try {
    const r = await hc(args);
    return r.code === 0 ? JSON.parse(r.stdout).address ?? null : null;
  } catch (_e) {
    return null;
  }
}

/** Is `address` a live core terminal? (`terminals()` is the app's live list.) */
export function alive(terminals, address) {
  return Boolean(address) && terminals.some((t) => t.address === address && t.state === "live");
}

/** Put nvim's cursor on `line`, at the top of its window. Quiet when nvim is gone. */
export async function jump(pad, nvimAddress, line) {
  if (!line) return;
  const { machine } = splitAddress(nvimAddress);
  const keys = `<C-\\><C-N>:${line}<CR>zt`;
  try {
    await exec("nvim", ["--server", pad.nvim.socket, "--remote-send", keys], { on: machine });
  } catch (_e) {
    // nvim exited between the click and now: the next Pad view starts a new one.
  }
}

/** End an nvim the panel started. */
export async function stopNvim(address) {
  try {
    await hc(["kill", address]);
  } catch (_e) {
    // already gone
  }
}
