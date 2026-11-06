// Eartag for the Herdr app: a pane on the right of an agent pane with what the conversation
// is about, the last ask and its outcome, files, quotas (Recap), and the tab's scratch pad
// marks (Pad). The herdr TUI's Eartag plugin, drawn natively.
//
// Opened by mods/eartag-key (Alt+I) as pane.split { mod: "eartag", props: { terminal } },
// terminal = the agent's address ("personal-agent-env/t18"). Data: `eartag.py json` on the
// agent's machine (data.js). Status comes live from agents(); the rest is polled gently.

import { View, div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { agents, props, run, shared, theme } from "herdr";
import { fetchPanel } from "./data.js";
import { padTab } from "./padtab.js";
import * as recap from "./recap.js";

const POLL_MS = 3000; // while the agent works, or right after its status changed
const IDLE_POLL_MS = 15000; // otherwise: timers keep running while the pane is hidden
const REGISTRY_KEY = "eartag.panels"; // KEEP IN SYNC with mods/eartag-key/toggle.js

const ERRORS = {
  unreachable: "Box unreachable",
  failed: "Eartag failed on the box",
};

export default class Eartag extends View {
  init(_p, cx) {
    // The pane's props come from herdr's props(), not init's argument.
    this.address = props()?.terminal ?? null;
    this.tab = "recap";
    this.result = null; // { doc, error?, detail? } of the last fetch
    this.busy = false;
    this.fetchedAt = 0;
    this.fetchedStatus = null;
    this.hoverBar = null;
    this.refresh(cx);
    cx.timer.every(POLL_MS, (cx) => this.tick(cx));
  }

  // -- data ------------------------------------------------------------------------
  /** The agent's status, live from Herdr (done/idle follow who looked); else the last doc's. */
  liveStatus() {
    const agent = agents().find((a) => a.address === this.address);
    return agent?.status ?? this.result?.doc?.view?.status ?? "unknown";
  }

  tick(cx) {
    const live = this.liveStatus();
    const stale = Date.now() - this.fetchedAt > IDLE_POLL_MS;
    if (live === "working" || live !== this.fetchedStatus || stale) this.refresh(cx);
  }

  refresh(cx) {
    this.address = this.address ?? props()?.terminal ?? null;
    if (this.busy || !this.address) return;
    this.busy = true;
    const live = this.liveStatus();
    cx.spawn(async (cx) => {
      const result = await fetchPanel(this.address);
      this.busy = false;
      this.fetchedAt = Date.now();
      this.fetchedStatus = live;
      // A failed fetch keeps showing the last good document, flagged as stale.
      this.result = result.doc ? result : { ...result, doc: this.result?.doc ?? null };
      cx.notify();
    });
  }

  // -- actions ---------------------------------------------------------------------
  /** This panel's pane id: from eartag-key's registry (panes() has no props). */
  myPane() {
    return (shared(REGISTRY_KEY) ?? {})[this.address] ?? props()?.pane ?? null;
  }

  /** nvim on the pad at the mark's line, in a split below this panel (on the agent's machine). */
  openPad(mark) {
    const pad = this.result?.doc?.pad;
    if (!pad) return;
    const argv = ["nvim", ...(mark.line ? [`+${mark.line}`] : []), pad.path];
    const pane = this.myPane();
    run("pane.split", pane ? { direction: "down", pane, argv } : { direction: "down", argv });
  }

  setTab(name, cx) {
    this.tab = name;
    cx.notify();
  }

  setHover(key, cx) {
    if (this.hoverBar === key) return;
    this.hoverBar = key;
    cx.notify();
  }

  // -- drawing ---------------------------------------------------------------------
  render() {
    const t = theme();
    const doc = this.result?.doc ?? null;
    return v_flex()
      .id("eartag")
      .size_full()
      .bg(t.background)
      .text_size(12.5)
      .text_color(t.foreground)
      .child(this.tabBar(t, doc))
      .child(this.body(t, doc));
  }

  tabBar(t, doc) {
    const marks = doc?.pad?.marks?.length ?? 0;
    return h_flex()
      .flex_none()
      .h(30)
      .px(12)
      .gap(16)
      .items_end()
      .border_b(1)
      .border_color(t.border)
      .child(this.tabButton(t, "recap", "Recap"))
      .child(this.tabButton(t, "pad", marks ? `Pad ${marks}` : "Pad"))
      .child(div().flex_1())
      .when(Boolean(this.result?.error && doc), (el) =>
        el.child(div().pb(7).text_size(10.5).text_color(t.dim).tooltip(this.result.detail ?? "").child("stale")),
      );
  }

  tabButton(t, name, label) {
    const on = this.tab === name;
    return div()
      .id(`tab-${name}`)
      .pb(6)
      .border_b(2)
      .border_color(on ? t.accent : t.background)
      .text_size(12)
      .font_semibold()
      .text_color(on ? t.foreground : t.dim)
      .cursor_pointer()
      .hover((s) => s.text_color(t.foreground))
      .on_click((_e, cx) => this.setTab(name, cx))
      .child(label);
  }

  body(t, doc) {
    const quiet = this.quietState(t, doc);
    if (quiet) return quiet;
    return this.tab === "pad" ? this.scroll(t, [padTab(t, doc.pad, (m) => this.openPad(m))]) : this.recapTab(t, doc.view);
  }

  /** Nothing to draw yet: no terminal, loading, or the box can't be reached. */
  quietState(t, doc) {
    if (doc) return null;
    const [title, detail] = !this.address
      ? ["No agent", "Open Eartag with Alt+I on an agent pane."]
      : this.result?.error
        ? [ERRORS[this.result.error] ?? "Unavailable", this.result.detail ?? ""]
        : ["Loading…", ""];
    return v_flex()
      .p(14)
      .gap(4)
      .child(div().text_color(t.muted).child(title))
      .child(div().text_size(11.5).text_color(t.dim).whitespace_normal().child(detail));
  }

  recapTab(t, v) {
    const live = this.liveStatus();
    const blocks = [
      recap.header(t, v, live),
      recap.notif(t, v, live),
      recap.main(t, v, live),
      recap.before(t, v),
      recap.files(t, v),
      recap.alerts(t, v),
    ].filter(Boolean);
    return v_flex()
      .flex_1()
      .min_h(0)
      .child(this.scroll(t, blocks))
      .child(div().flex_none().px(12).pb(10).child(recap.footer(t, v, this.hoverBar, (key, cx) => this.setHover(key, cx))));
  }

  scroll(t, children) {
    return v_flex().id(`scroll-${this.tab}`).flex_1().min_h(0).overflow_y_scrollbar().p(12).gap(14).children(children);
  }
}
