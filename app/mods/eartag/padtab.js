// The Pad tab: the tab's scratch pad, one line per ` mark with its title. The whole line is
// clickable and lights up on hover; a click opens the pad in nvim at that mark's line.
// Read only, like the TUI: the panel never writes a pad (Silvio edits it in that nvim).

import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { heading } from "./recap.js";
import { role } from "./style.js";

/** pad: doc.pad (null when `scratch --path` resolved none); onOpen(mark) opens nvim. */
export function padTab(t, pad, onOpen) {
  if (!pad) {
    return v_flex()
      .gap(4)
      .child(div().text_color(t.muted).child("No scratch pad for this tab."))
      .child(div().text_size(11.5).text_color(t.dim).whitespace_normal().child("`scratch` starts one in the agent's tab."));
  }
  const todo = pad.todo ? `☐ ${pad.todo.done}/${pad.todo.total}` : "";
  return v_flex()
    .gap(6)
    .child(heading(t, pad.name, todo))
    .when(!pad.marks.length, (el) => el.child(div().text_color(t.dim).child("No ` marks in this pad yet.")))
    .child(v_flex().gap(1).children(pad.marks.map((m) => markRow(t, m, onOpen))));
}

function markRow(t, m, onOpen) {
  const look = role(t, m.role);
  return h_flex()
    .id(`mark-${m.letter}`)
    .gap(8)
    .px(6)
    .py(4)
    .rounded(5)
    .items_center()
    .cursor_pointer()
    .hover((s) => s.bg(t.hover))
    .on_click((_e, cx) => {
      cx.stop_propagation();
      onOpen(m);
    })
    .child(div().flex_none().w(18).font_semibold().text_color(look.color).child("`" + m.letter))
    .child(
      div()
        .flex_1()
        .truncate()
        .text_color(look.color)
        .when(look.bold, (el) => el.font_semibold())
        .child(m.title || "—"),
    )
    .when(Boolean(m.count), (el) => el.child(div().flex_none().text_size(11).text_color(t.muted).child(m.count)));
}
