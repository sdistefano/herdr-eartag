// Pure helpers (no herdr imports, testable with node --test): which agent the panel is
// about, and the click-level layout commands for the Pad tab.
//
// The layout holds Eartag like Files and Changes: a child of the right `panel-body` stack,
//   { id: "eartag", type: "column", children: [
//       { id: "eartag-view", content: { mod: "eartag" } },
//       { id: "eartag-pad", hidden: true, content: { terminal: "<machine>/eartag-pad" } } ] }
// The Pad tab shows `eartag-pad` (the named nvim, nvim.js) and shrinks the panel to its tab
// bar; Recap hides it again. Only show/hide/resize: `layout.set` would wipe the person's clicks.

export const COLUMN_ID = "eartag";
export const VIEW_ID = "eartag-view";
export const PAD_ID = "eartag-pad";
export const TABBAR_PX = 31; // the panel's tab bar (30) and its border

/** The node with `id` in a layout tree, or null. */
export function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

/** The machine whose nvim the layout's pad block shows, or null (no block). */
export function padMachine(root) {
  const terminal = find(root, PAD_ID)?.content?.terminal;
  return terminal ? splitAddress(terminal).machine : null;
}

/**
 * The layout file's tree with the pad block showing `terminal` ("<machine>/eartag-pad"), or
 * null when nothing needs to change (or the layout has no Eartag column). The app drops a
 * terminal block from the file when its terminal ends (nvim quit), so the panel puts it back.
 */
export function withPadBlock(tree, terminal) {
  if (!find(tree, COLUMN_ID) || find(tree, PAD_ID)?.content?.terminal === terminal) return null;
  const copy = JSON.parse(JSON.stringify(tree)); // the mod runtime has no structuredClone
  const column = find(copy, COLUMN_ID);
  const block = { id: PAD_ID, type: "block", hidden: true, content: { terminal } };
  column.children = [...(column.children ?? []).filter((c) => c.id !== PAD_ID), block];
  return copy;
}

/** The commands that make the layout show the pad's nvim (show) or the panel alone, as
 *  [name, args] pairs; only what differs from now. */
export function padSteps(root, show) {
  const pad = find(root, PAD_ID);
  const view = find(root, VIEW_ID);
  if (!pad || !view) return [];
  const steps = [];
  if (Boolean(pad.hidden) === show) steps.push([show ? "layout.show" : "layout.hide", { id: PAD_ID }]);
  const shrunk = view.size?.px === TABBAR_PX;
  if (shrunk !== show) steps.push(["layout.resize", show ? { id: VIEW_ID, px: TABBAR_PX } : { id: VIEW_ID, weight: 1 }]);
  return steps;
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
