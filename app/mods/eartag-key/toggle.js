// What Alt+I does, as plain data (no herdr imports, so it is testable with node --test).
//
// The registry maps an agent's terminal address ("personal-agent-env/t18") to the pane id
// of its Eartag panel. `panes()` does not expose a mod pane's props, so this is how a
// panel is found again; it lives in shared("eartag.panels") so every copy sees it.

export const PANEL_MOD = "eartag";
export const REGISTRY_KEY = "eartag.panels";

/** Is `id` a live Eartag pane? */
const isPanel = (panes, id) => panes.some((p) => p.pane === id && p.mod === PANEL_MOD);

/** The registry entry ([terminal, pane]) whose panel is `paneId`, if any. */
export function ownerOf(registry, paneId) {
  return Object.entries(registry).find(([, pane]) => pane === paneId) ?? null;
}

/**
 * The action for one press:
 *   { kind: "close", pane, terminal }  the focused agent's panel, or the focused panel itself
 *   { kind: "open", pane, terminal }   split a panel to the right of the focused agent pane
 *   { kind: "none" }                   nothing focused that a panel can be about
 */
export function plan(focused, panes, registry) {
  const pane = focused?.pane;
  if (!pane) return { kind: "none" };
  const own = ownerOf(registry, pane);
  const focusedIsPanel = own || isPanel(panes, pane);
  if (focusedIsPanel) return { kind: "close", pane, terminal: own?.[0] ?? null };
  const terminal = focused.terminal;
  if (!terminal) return { kind: "none" };
  const panel = registry[terminal];
  if (panel && isPanel(panes, panel)) return { kind: "close", pane: panel, terminal };
  return { kind: "open", pane, terminal };
}

/** The Eartag pane in `tab` that is in `after` but was not in `before` (the one just split). */
export function newPanel(before, after, tab) {
  const old = new Set(before.map((p) => p.pane));
  return after.find((p) => p.mod === PANEL_MOD && p.tab === tab && !old.has(p.pane))?.pane ?? null;
}

/** The registry without entries whose panel pane is gone (closed with its header's ×, its tab closed). */
export function prune(registry, panes) {
  return Object.fromEntries(Object.entries(registry).filter(([, pane]) => isPanel(panes, pane)));
}

/** "personal-agent-env/t18" -> { machine: "personal-agent-env", local: "t18" }; "t2" -> machine null. */
export function splitAddress(address) {
  const cut = (address ?? "").lastIndexOf("/");
  return cut < 0 ? { machine: null, local: address ?? "" } : { machine: address.slice(0, cut), local: address.slice(cut + 1) };
}
