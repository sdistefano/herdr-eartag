// Getting the panel's data: `eartag.py json --terminal tN`, run on the agent's machine.
// Everything (transcripts, quotas, pads, repos) lives where the agent runs, so the mod
// never reads files itself: one exec per refresh, on that machine.

import { exec } from "herdr";

// Relative to the home folder of the machine it runs on (exec starts there).
export const SCRIPT = "proj/herdr-eartag/eartag.py";

/** "personal-agent-env/t18" -> { machine: "personal-agent-env", local: "t18" }; "t2" -> machine null.
 *  KEEP IN SYNC with mods/eartag-key/toggle.js (a mod cannot import another mod's files). */
export function splitAddress(address) {
  const cut = (address ?? "").lastIndexOf("/");
  return cut < 0 ? { machine: null, local: address ?? "" } : { machine: address.slice(0, cut), local: address.slice(cut + 1) };
}

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
