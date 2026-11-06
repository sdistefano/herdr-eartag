// Eartag for the Herdr app: a side panel, like Files and Changes, about the focused agent:
// what the conversation is about, the last ask and how it went, files, quotas (Recap), and
// the tab's scratch pad (Pad): a real nvim on it, filling the panel under its tab bar.
//
// Lives in the layout as the `eartag` child of the right `panel-body` stack (see layout.js);
// Alt+I (mods/eartag-key) shows or hides it. Data: `eartag.py json` on the agent's machine
// (data.js). Status comes live from agents(); the rest is fetched only while it shows.

import { View, div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { agents, focused, layout, run, terminals, theme } from "herdr";
import { fetchPanel, startPad } from "./data.js";
import { COLUMN_ID, agentFor, find, padMachine, padSteps, splitAddress } from "./layout.js";
import { showPad } from "./nvim.js";
import { padTab } from "./padtab.js";
import * as recap from "./recap.js";

const TICK_MS = 1000; // cheap: follows focus; fetching is paced below
const POLL_MS = 3000; // while the agent works, or right after its status changed
const IDLE_POLL_MS = 15000; // otherwise
const NVIM_CHECK_MS = 10000; // how often the Pad tab checks its nvim is still running

const ERRORS = {
  unreachable: "Box unreachable",
  failed: "Eartag failed on the box",
};

export default class Eartag extends View {
  init(_p, cx) {
    this.tab = "recap";
    this.address = null; // the agent shown now
    this.lastByTab = {}; // tab -> agent last focused there
    this.results = {}; // address -> { doc, error?, detail?, at, status }
    this.busy = new Set(); // addresses being fetched
    this.nvim = { file: null, at: 0, busy: false, error: null }; // the named pad nvim
    this.padStarts = {}; // address -> "running" | { error, detail }: one try per agent
    this.hoverBar = null;
    this.tick(cx);
    cx.timer.every(TICK_MS, (cx) => this.tick(cx));
  }

  // -- what to show ----------------------------------------------------------------
  /** The panel is the shown child of a visible panel column. */
  visible() {
    const root = layout();
    const panel = find(root, "panel");
    const body = find(root, "panel-body");
    return Boolean(find(root, COLUMN_ID)) && !panel?.hidden && (!body || body.active === COLUMN_ID);
  }

  result() {
    return this.results[this.address] ?? null;
  }

  liveStatus() {
    const agent = agents().find((a) => a.address === this.address);
    return agent?.status ?? this.result()?.doc?.view?.status ?? "unknown";
  }

  tick(cx) {
    const address = agentFor(focused(), agents(), this.lastByTab);
    if (address !== this.address) {
      this.address = address;
      this.hoverBar = null;
      cx.notify();
    }
    if (!this.visible()) return;
    if (this.due()) this.refresh(cx);
    this.syncPad(cx);
  }

  due() {
    const r = this.result();
    if (!r) return true;
    const live = this.liveStatus();
    return live !== r.status || Date.now() - r.at > (live === "working" ? POLL_MS : IDLE_POLL_MS);
  }

  refresh(cx) {
    const address = this.address;
    if (!address || this.busy.has(address)) return;
    this.busy.add(address);
    const status = this.liveStatus();
    cx.spawn(async (cx) => {
      const fetched = await fetchPanel(address);
      this.busy.delete(address);
      // A failed fetch keeps showing the last good document, flagged as stale.
      const doc = fetched.doc ?? this.results[address]?.doc ?? null;
      this.results[address] = { ...fetched, doc, at: Date.now(), status };
      cx.notify();
      this.syncPad(cx);
    });
  }

  // -- the pad's nvim --------------------------------------------------------------
  /** On the Pad tab, the layout shows the named nvim on this agent's pad, the panel shrunk to
   *  its tab bar; otherwise the panel alone. Pads with no nvim to show keep their message. */
  syncPad(cx) {
    this.ensurePad(cx);
    const root = layout();
    const pad = this.result()?.doc?.pad;
    const machine = splitAddress(this.address).machine;
    const onBox = Boolean(machine) && machine === padMachine(root);
    const wanted = this.tab === "pad" && this.visible() && pad?.nvim && onBox ? pad : null;
    if (wanted) this.checkNvim(wanted, machine, cx);
    const ready = wanted && !this.nvim.error && this.nvim.file === wanted.path;
    for (const [name, args] of padSteps(root, Boolean(ready))) run(name, args);
  }

  /** Start the nvim or point it at this pad, when the pad changed or now and then. */
  checkNvim(pad, machine, cx) {
    const n = this.nvim;
    const fresh = n.file === pad.path && Date.now() - n.at < NVIM_CHECK_MS;
    if (n.busy || fresh) return;
    n.busy = true;
    cx.spawn(async (cx) => {
      n.error = await showPad(machine, pad, n.file);
      n.file = n.error ? null : pad.path;
      n.at = Date.now();
      n.busy = false;
      cx.notify();
      this.syncPad(cx);
    });
  }

  // -- actions ---------------------------------------------------------------------
  setTab(name, cx) {
    this.tab = name;
    cx.notify();
    this.syncPad(cx);
  }

  setHover(key, cx) {
    if (this.hoverBar === key) return;
    this.hoverBar = key;
    cx.notify();
  }

  // -- drawing ---------------------------------------------------------------------
  render() {
    const t = theme();
    const doc = this.result()?.doc ?? null;
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
    const r = this.result();
    return h_flex()
      .flex_none()
      .h(30)
      .px(12)
      .gap(16)
      .items_end()
      .border_b(1)
      .border_color(t.border)
      .child(this.tabButton(t, "recap", "Recap"))
      .child(this.tabButton(t, "pad", "Pad"))
      .child(div().flex_1())
      .when(Boolean(r?.error && doc), (el) => el.child(div().pb(7).text_size(10.5).text_color(t.dim).tooltip(r.detail ?? "").child("stale")));
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
    if (this.tab === "pad") {
      const machine = splitAddress(this.address).machine;
      const status = { starting: this.padStarts[this.address], nvimError: this.nvim.error, offBox: machine !== padMachine(layout()) };
      return this.scroll(t, [padTab(t, doc.pad, status)]);
    }
    return this.recapTab(t, doc.view);
  }

  /** Nothing to draw yet: no agent in the tab, loading, or the box can't be reached. */
  quietState(t, doc) {
    if (doc) return null;
    const r = this.result();
    const [title, detail] = !this.address
      ? ["No agent in this tab", "Eartag follows the agent you focus."]
      : r?.error
        ? [ERRORS[r.error] ?? "Unavailable", r.detail ?? ""]
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
