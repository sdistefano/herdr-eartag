// eartag-key: Alt+I shows or hides the Eartag side panel (like prefix+i with the herdr TUI's
// Eartag plugin). The panel follows the focused agent by itself.
//
// keys.json: "global": { "alt-i": "eartag-key.toggle" }. It takes two layout commands, so a
// tiny always-present companion runs them: a 1 px block in the layout that draws nothing
// (like zoom-swap). The decision is in toggle.js.

import { View, div } from "gpui-kit";
import { layout, nextCommand, notify, run, setShared, shared, theme } from "herdr";
import { CHILD, steps } from "./toggle.js";

// The shipped tab bar remembers the side panel per space, but restores only the panels
// listed here (the welcome's "workspace.panels"): without Eartag in it, a space switch
// would close Eartag. Its buttons are still drawn only for files and changes.
const PANELS_KEY = "workspace.panels";
const DEFAULT_PANELS = ["files", "changes"];

export default class EartagKey extends View {
  init(_props, cx) {
    const panels = shared(PANELS_KEY) ?? DEFAULT_PANELS;
    if (!panels.includes(CHILD)) setShared(PANELS_KEY, [...panels, CHILD]);
    cx.spawn(async () => {
      for (;;) if ((await nextCommand()) === "toggle") this.toggle();
    });
  }

  toggle() {
    const todo = steps(layout());
    if (!todo.length) notify({ title: "Eartag", body: "This layout has no Eartag panel.", level: "warning" });
    for (const [name, args] of todo) run(name, args);
  }

  render() {
    return div().id("eartag-key").size_full().bg(theme().canvas);
  }
}
