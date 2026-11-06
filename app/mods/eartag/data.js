// Getting the panel's data: `eartag.py json --terminal tN`, run on the agent's machine.
// Everything (transcripts, quotas, pads, repos) lives where the agent runs, so the mod
// never reads files itself: one exec per refresh, on that machine.

import { exec } from "herdr";
import { splitAddress } from "./layout.js";

// Relative to the home folder of the machine it runs on (exec starts there).
export const SCRIPT = "proj/herdr-eartag/eartag.py";


/** { doc } on success; { error, detail } when the machine is unreachable or eartag fails.
 *  Never throws: the panel shows a quiet state instead. */
export async function fetchPanel(address) {
  const { machine, local } = splitAddress(address);
  let result;
  try {
    result = await exec("python3", [SCRIPT, "json", "--terminal", local], { on: machine });
  } catch (e) {
    return { error: "unreachable", detail: String(e?.message ?? e) };
  }
  if (result.code !== 0) return { error: "failed", detail: lastLine(result.stderr) };
  try {
    return { doc: JSON.parse(result.stdout) };
  } catch (_e) {
    return { error: "failed", detail: "eartag.py printed no JSON" };
  }
}

const lastLine = (text) => String(text ?? "").trim().split("\n").pop() || "exit code without output";

/** Create the agent's tab pad (`eartag.py pad-start`): { path } or { error, detail }. */
export async function startPad(address) {
  const { machine, local } = splitAddress(address);
  try {
    const r = await exec("python3", [SCRIPT, "pad-start", "--terminal", local], { on: machine });
    const out = JSON.parse(r.stdout || "{}");
    return out.path ? { path: out.path } : { error: out.error ?? "failed", detail: out.detail ?? lastLine(r.stderr) };
  } catch (e) {
    return { error: "unreachable", detail: String(e?.message ?? e) };
  }
}
