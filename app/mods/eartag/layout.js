// Pure helpers (no herdr imports, testable with node --test): which agent the panel is
// about, and the layout edit that shows the pad's nvim under the panel.
//
// The layout holds Eartag like Files and Changes: a child of the right `panel-body` stack,
//   { id: "eartag", type: "column", children: [ { id: "eartag-view", content: { mod: "eartag" } } ] }
// and on the Pad tab a terminal block is added under it: { id: "eartag-pad", content: { terminal } }.

export const COLUMN_ID = "eartag";
export const PAD_ID = "eartag-pad";
const PAD_WEIGHT = 3; // nvim gets three shares, the marks list one

/** The node with `id` in a layout tree, or null. */
export function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

/** The terminal the pad block shows now, or null when there is none. */
export function padTerminal(root) {
  return find(root, PAD_ID)?.content?.terminal ?? null;
}

/** A copy of the tree whose Eartag column shows `terminal` under the panel (null: no pad
 *  block). Returns null when the layout has no Eartag column (nothing to edit). */
export function withPad(root, terminal) {
  if (!find(root, COLUMN_ID)) return null;
  const copy = structuredClone(root);
  const column = find(copy, COLUMN_ID);
  column.children = (column.children ?? []).filter((c) => c.id !== PAD_ID);
  if (terminal) column.children.push({ id: PAD_ID, type: "block", content: { terminal }, size: { weight: PAD_WEIGHT } });
  return copy;
}

/**
 * The agent the panel is about: the focused terminal when it is an agent; else the agent
 * last focused in this tab (the person clicked the pad's nvim or a shell); else the tab's
 * first agent. `lastByTab` is updated in place. Returns an address or null.
 */
export function agentFor(focused, agents, lastByTab) {
  const tab = focused?.tab;
  if (!tab) return null;
  const inTab = agents.filter((a) => a.tab === tab);
  const here = inTab.find((a) => a.address === focused.terminal);
  if (here) lastByTab[tab] = here.address;
  const last = inTab.find((a) => a.address === lastByTab[tab]);
  return (here ?? last ?? inTab[0])?.address ?? null;
}

/** "personal-agent-env/t18" -> { machine: "personal-agent-env", local: "t18" }; "t2" -> machine null. */
export function splitAddress(address) {
  const cut = (address ?? "").lastIndexOf("/");
  return cut < 0 ? { machine: null, local: address ?? "" } : { machine: address.slice(0, cut), local: address.slice(cut + 1) };
}
