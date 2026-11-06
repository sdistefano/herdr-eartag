// eartag-key: Alt+I shows or hides the Eartag panel on the right of the focused agent pane,
// like prefix+i with the herdr TUI's Eartag plugin.
//
// keys.json: "global": { "alt-i": "eartag-key.toggle" }. `<mod>.<command>` reaches shown
// copies only, and the first panel does not exist yet, so this always-present companion
// receives the key: a 1 px block in the layout that draws nothing (like zoom-swap).
// The decision is in toggle.js.

import { View, div } from "gpui-kit";
import { focused, panes, run, nextCommand, shared, setShared, theme } from "herdr";
import { PANEL_MOD, REGISTRY_KEY, newPanel, plan, prune } from "./toggle.js";

const FIND_TRIES = 10; // a split on another machine may reach panes() a moment later
const FIND_EVERY_MS = 150;

export default class EartagKey extends View {
  init(_props, cx) {
    cx.spawn(async (cx) => {
      for (;;) if ((await nextCommand()) === "toggle") this.toggle(cx);
    });
  }

  /** One Alt+I press: close the panel the focus is about, or open one. */
  toggle(cx) {
    const registry = prune(shared(REGISTRY_KEY) ?? {}, panes());
    const step = plan(focused(), panes(), registry);
    const actions = {
      none: () => setShared(REGISTRY_KEY, registry),
      close: () => this.close(step, registry),
      open: () => this.open(step, registry, cx),
    };
    actions[step.kind]();
  }

  close(step, registry) {
    run("pane.close", { pane: step.pane });
    if (step.terminal) delete registry[step.terminal];
    setShared(REGISTRY_KEY, registry);
  }

  open(step, registry, cx) {
    const tab = focused()?.tab;
    const before = panes();
    run("pane.split", { direction: "right", pane: step.pane, mod: PANEL_MOD, props: { terminal: step.terminal } });
    this.remember(step.terminal, before, tab, registry, cx, FIND_TRIES);
  }

  /** Record the new panel's pane id once panes() shows it. */
  remember(terminal, before, tab, registry, cx, tries) {
    const pane = newPanel(before, panes(), tab);
    if (pane) {
      setShared(REGISTRY_KEY, { ...registry, [terminal]: pane });
      return;
    }
    if (tries > 0) cx.timer.after(FIND_EVERY_MS, (cx) => this.remember(terminal, before, tab, registry, cx, tries - 1));
  }

  render() {
    return div().id("eartag-key").size_full().bg(theme().canvas);
  }
}
