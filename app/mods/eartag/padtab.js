// The Pad tab's own text, for when there is no nvim to show: the pad is being started, could
// not be, or the agent is not on the machine the layout's nvim block shows. Otherwise the
// panel shrinks to its tab bar and the real nvim on the pad fills it (nvim.js, layout.js).

import { div } from "gpui-kit";
import { v_flex } from "gpui-base";

/** pad: doc.pad (null while the tab has none). status.starting: "running" | "done" |
 *  { error, detail }; status.nvimError: why nvim could not start; status.offBox: no nvim
 *  block for this agent's machine. */
export function padTab(t, pad, status = {}) {
  const failed = status.starting && typeof status.starting === "object";
  const [title, detail, bad] = status.offBox
    ? ["The pad nvim runs on the box.", "This agent is on another machine.", false]
    : failed
      ? ["Could not start a scratch pad.", status.starting.detail ?? "", true]
      : !pad
        ? ["Starting a scratch pad for this tab…", "", false]
        : status.nvimError
          ? ["Could not open nvim on the pad.", status.nvimError, true]
          : ["Opening nvim…", pad.path, false];
  return v_flex()
    .gap(4)
    .child(div().text_color(bad ? t.blocked : t.muted).child(title))
    .when(Boolean(detail), (el) => el.child(div().text_size(11.5).text_color(t.dim).whitespace_normal().child(detail)));
}
