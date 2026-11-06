// What Alt+I does, as plain data (no herdr imports, testable with node --test).
//
// Eartag is a side panel like Files and Changes: the `eartag` child of the right
// `panel-body` stack, inside the `panel` column. Alt+I hides that column when Eartag is the
// one showing, else selects Eartag and shows the column (what the tab bar's Changes button does).

export const PANEL = "panel";
export const STACK = "panel-body";
export const CHILD = "eartag";

function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

/** The commands for one press, as [name, args] pairs; [] when the layout has no Eartag. */
export function steps(root) {
  const stack = find(root, STACK);
  if (!find(stack, CHILD)) return [];
  const shown = !find(root, PANEL)?.hidden && stack.active === CHILD;
  if (shown) return [["layout.hide", { id: PANEL }]];
  return [
    ["layout.select", { stack: STACK, child: CHILD }],
    ["layout.show", { id: PANEL }],
  ];
}
