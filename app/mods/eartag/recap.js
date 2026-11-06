// The Recap tab: the same blocks as the TUI panel, drawn from `doc.view` (eartag.py json).
// Each block is a small function (t = theme(), v = view data); main.js stacks them.

import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { SPIN, effort, gauge, plain, role, status, verdict } from "./style.js";

/** A small all-caps block title, with optional text on the right. */
export function heading(t, title, right) {
  return h_flex()
    .justify_between()
    .text_size(10.5)
    .font_semibold()
    .text_color(t.dim)
    .child(div().child(String(title).toUpperCase()))
    .when(Boolean(right), (el) => el.child(div().font_medium().child(right)));
}

/** A colored pill ("◐ WORKING", "bypass"). */
export function chip(t, text, color, spin = false) {
  return h_flex()
    .flex_none()
    .px(6)
    .h(18)
    .gap(4)
    .items_center()
    .rounded(5)
    .bg(color + "26")
    .text_size(10.5)
    .font_semibold()
    .text_color(color)
    .when(spin, (el) => el.child(div().frames(SPIN, 90).child(SPIN[0])))
    .child(div().child(text));
}

/** Project, permission mode and the agent's live status. */
export function header(t, v, live) {
  const st = status(t, live);
  return h_flex()
    .gap(6)
    .items_center()
    .child(div().flex_1().truncate().text_size(14).font_semibold().text_color(t.foreground).child(v.project || "—"))
    .when(Boolean(v.mode_tag), (el) => el.child(chip(t, v.mode_tag, v.mode_tag === "bypass" ? t.blocked : t.muted)))
    .child(chip(t, st.label, st.color, live === "working"));
}

/** "Your turn: …" under the header, when the agent waits for the person. */
export function notif(t, v, live) {
  if (!v.notif || !["done", "blocked"].includes(live)) return null;
  return div().text_size(12).font_medium().text_color(role(t, v.notif.role).color).child(v.notif.text);
}

/** Now / last ask: the ask (with its verdict when rephrasing gave one), the tool running,
 *  task progress. The agent's reply itself is left out: it is right there in the agent pane. */
export function main(t, v, live) {
  if (v.main_kind === "none") {
    return v_flex().gap(2).children((v.message_lines ?? []).map((line) => div().text_color(t.muted).child(line)));
  }
  return v_flex()
    .gap(6)
    .child(askHeading(t, v))
    .when(Boolean(v.session_title), (el) => el.child(div().text_size(11.5).text_color(t.muted).truncate().child(v.session_title)))
    .child(div().text_size(13).text_color(t.foreground).whitespace_normal().child(plain(v.ask)))
    .children((v.ask_points ?? []).map((p) => div().text_color(t.muted).child("· " + plain(p))))
    .when(Boolean(v.activity), (el) => el.child(activity(t, v, live)))
    .when(Boolean(v.tasks), (el) => el.child(tasks(t, v.tasks)));
}

/** NOW / LAST ASK, its verdict chip, and how long ago it was asked. */
function askHeading(t, v) {
  const tag = verdict(t, v.reply_verdict);
  return h_flex()
    .gap(6)
    .items_center()
    .child(div().flex_1().child(heading(t, v.main_title, v.main_right)))
    .when(Boolean(tag), (el) => el.child(chip(t, tag.label, tag.color)));
}

function activity(t, v, live) {
  const working = live === "working" && v.activity_role !== "blocked";
  const color = working ? t.working : role(t, v.activity_role).color;
  return h_flex()
    .gap(6)
    .items_center()
    .text_size(12)
    .text_color(color)
    .child(div().flex_none().w(12).when(working, (el) => el.frames(SPIN, 90)).child(working ? SPIN[0] : "▸"))
    .child(div().flex_1().truncate().child(v.activity));
}

function tasks(t, k) {
  const pct = k.total ? Math.round((k.done / k.total) * 100) : 0;
  return v_flex()
    .gap(3)
    .child(
      h_flex()
        .justify_between()
        .text_size(11.5)
        .text_color(t.muted)
        .child(div().flex_1().truncate().child(k.now || "tasks"))
        .child(div().flex_none().child(`${k.done}/${k.total}`)),
    )
    .child(track(t, pct, t.accent));
}


/** Three previous asks, each with its outcome glyph when rephrasing gave one. */
export function before(t, v) {
  if (!v.before?.length) return null;
  return v_flex()
    .gap(3)
    .child(heading(t, v.before_title || "before"))
    .children(
      v.before.map((row) => {
        const tag = verdict(t, row.verdict);
        return h_flex()
          .gap(6)
          .text_size(12)
          .child(div().flex_none().w(12).text_color(tag?.color ?? t.dim).child(tag?.glyph ?? "·"))
          .child(div().flex_none().text_color(t.dim).child(row.time))
          .child(div().flex_1().truncate().text_color(t.muted).child(plain(row.title)));
      }),
    );
}

/** Files edited in the session, with the repository's uncommitted +/− lines. */
export function files(t, v) {
  if (!v.files?.length) return null;
  const diff = v.diff ? `+${v.diff.added} −${v.diff.removed}` : "";
  return v_flex()
    .gap(2)
    .child(heading(t, v.files_title || "files", diff))
    .children(v.files.slice(0, 8).map((f) => div().text_size(12).truncate().text_color(t.foreground).child(f)))
    .when(v.files.length > 8, (el) => el.child(div().text_size(11.5).text_color(t.dim).child(`+${v.files.length - 8} more`)));
}

export function alerts(t, v) {
  if (!v.alerts?.length) return null;
  return v_flex().gap(2).children(v.alerts.map((a) => div().text_size(12).text_color(t.working).child("⚠ " + a)));
}

/** A thin progress track filled to pct %. */
function track(t, pct, color) {
  const fill = Math.max(0, Math.min(100, pct ?? 0));
  return div()
    .h(5)
    .w_full()
    .rounded(3)
    .bg(t.raised)
    .child(div().h_full().w(`${fill}%`).rounded(3).bg(color));
}

/** Context, 5h and 7d gauges; hovering one shows its detail (reset time) in place of the
 *  machine line, so nothing moves. */
export function footer(t, v, hovered, onHover) {
  const bars = v.bars ?? [];
  const shown = bars.find((b) => b.key === hovered);
  return v_flex()
    .gap(5)
    .pt(8)
    .border_t(1)
    .border_color(t.border)
    .children(bars.map((b) => gaugeRow(t, b, onHover)))
    .child(shown ? detail(t, shown) : meta(t, v))
    .when(Boolean(v.footnote), (el) => el.child(div().text_size(11).text_color(t.dim).whitespace_normal().child(v.footnote)));
}

function gaugeRow(t, b, onHover) {
  const color = gauge(t, b.pct);
  return h_flex()
    .id(`gauge-${b.key}`)
    .gap(8)
    .items_center()
    .text_size(11)
    .on_hover((on, cx) => onHover(on ? b.key : null, cx))
    .child(div().flex_none().w(30).font_semibold().text_color(t.dim).child(b.label))
    .child(div().flex_1().child(track(t, b.pct, color)))
    .child(div().flex_none().w(34).text_right().text_color(color).child(`${Math.round(b.pct)}%`));
}

function detail(t, b) {
  return h_flex()
    .gap(4)
    .text_size(11)
    .child(div().text_color(t.foreground).child(b.detail || b.label))
    .child(div().text_color(t.dim).child(b.detail_sub || ""));
}

/** machine · branch · model effort-dots */
function meta(t, v) {
  const dots = effort(t, v.effort_level);
  const where = [v.host, v.branch].filter(Boolean).join(" · ");
  return h_flex()
    .gap(6)
    .text_size(11)
    .items_center()
    .child(div().flex_1().truncate().text_color(t.dim).child(where))
    .when(Boolean(v.model), (el) => el.child(div().flex_none().text_color(t.muted).child([v.model, v.version].filter(Boolean).join(" "))))
    .when(Boolean(v.effort), (el) => el.child(div().flex_none().text_color(dots?.color ?? t.muted).child(v.effort)))
    .when(Boolean(dots), (el) => el.child(div().flex_none().text_size(9).text_color(dots.color).child(dots.dots)));
}
