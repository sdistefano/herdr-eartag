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

/** The node that is shown and hidden: the `panel` column, or the stack itself when the app
 *  collapsed that single-child column into it (it does when it rewrites the layout file). */
export const panelNode = (root) => find(root, PANEL) ?? find(root, STACK);

/** The commands for one press, as [name, args] pairs; [] when the layout has no Eartag. */
export function steps(root) {
  const stack = find(root, STACK);
  if (!find(stack, CHILD)) return [];
  const panel = panelNode(root);
  if (!panel.hidden && stack.active === CHILD) return [["layout.hide", { id: panel.id }]];
  return [
    ["layout.select", { stack: STACK, child: CHILD }],
    ["layout.show", { id: panel.id }],
  ];
}
