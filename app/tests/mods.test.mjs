// node --test app/tests: the pure parts of the Herdr app mods (no herdr runtime needed).
import { test } from "node:test";
import assert from "node:assert/strict";
import { steps } from "../mods/eartag-key/toggle.js";
import { agentFor, padTerminal, splitAddress, withPad } from "../mods/eartag/layout.js";
import { effort, gauge, plain, role, status, verdict } from "../mods/eartag/style.js";

const tree = (hidden, active, pad) => ({
  id: "root",
  children: [
    {
      id: "panel",
      hidden,
      children: [
        {
          id: "panel-body",
          type: "stack",
          active,
          children: [
            { id: "changes" },
            { id: "eartag", type: "column", children: [{ id: "eartag-view" }, ...(pad ? [{ id: "eartag-pad", content: { terminal: pad } }] : [])] },
          ],
        },
      ],
    },
  ],
});

test("Alt+I shows Eartag when the panel is hidden", () => {
  assert.deepEqual(steps(tree(true, "eartag")), [
    ["layout.select", { stack: "panel-body", child: "eartag" }],
    ["layout.show", { id: "panel" }],
  ]);
});

test("Alt+I switches from Changes to Eartag", () => {
  assert.equal(steps(tree(false, "changes"))[0][0], "layout.select");
});

test("Alt+I hides Eartag when it shows", () => {
  assert.deepEqual(steps(tree(false, "eartag")), [["layout.hide", { id: "panel" }]]);
});

test("Alt+I does nothing in a layout without Eartag", () => {
  assert.deepEqual(steps({ id: "root", children: [] }), []);
});

test("withPad adds, swaps and removes the nvim block without touching the input", () => {
  const root = tree(false, "eartag");
  const one = withPad(root, "box/t30");
  assert.equal(padTerminal(one), "box/t30");
  assert.equal(padTerminal(root), null);
  assert.equal(padTerminal(withPad(one, "box/t31")), "box/t31");
  assert.equal(padTerminal(withPad(one, null)), null);
  assert.equal(withPad({ id: "root" }, "box/t30"), null);
});

const A = [
  { address: "box/t2", tab: "tb1" },
  { address: "box/t5", tab: "tb1" },
  { address: "box/t18", tab: "tb2" },
];

test("the panel follows the focused agent", () => {
  assert.equal(agentFor({ tab: "tb2", terminal: "box/t18" }, A, {}), "box/t18");
});

test("focusing a shell or the pad nvim keeps the agent last focused in that tab", () => {
  const last = {};
  agentFor({ tab: "tb1", terminal: "box/t5" }, A, last);
  assert.equal(agentFor({ tab: "tb1", terminal: "box/t30" }, A, last), "box/t5");
});

test("a tab never focused shows its first agent; a tab without agents none", () => {
  assert.equal(agentFor({ tab: "tb1", terminal: "box/t9" }, A, {}), "box/t2");
  assert.equal(agentFor({ tab: "tb9", terminal: "t1" }, A, {}), null);
});

test("splitAddress strips the machine prefix", () => {
  assert.deepEqual(splitAddress("personal-agent-env/t18"), { machine: "personal-agent-env", local: "t18" });
  assert.deepEqual(splitAddress("t2"), { machine: null, local: "t2" });
});

const T = { done: "#0f0", working: "#fa0", blocked: "#f00", idle: "#888", dim: "#555", muted: "#777", accent: "#09f", foreground: "#fff", ansi3: "#ff0", ansi6: "#0ff" };

test("verdicts map to theme colors and labels", () => {
  assert.deepEqual(verdict(T, "WAITING"), { label: "? YOUR TURN", color: "#f00", glyph: "?" });
  assert.equal(verdict(T, ""), null);
});

test("roles carry color and weight", () => {
  assert.deepEqual(role(T, "working b"), { color: "#fa0", bold: true });
  assert.deepEqual(role(T, "dim"), { color: "#555", bold: false });
  assert.deepEqual(role(T, "nonsense"), { color: "#fff", bold: false });
});

test("status falls back for unknown states", () => {
  assert.deepEqual(status(T, "blocked"), { label: "NEEDS YOU", color: "#f00" });
  assert.deepEqual(status(T, "weird"), { label: "—", color: "#555" });
});

test("gauges turn gold at 70 and red at 90", () => {
  assert.equal(gauge(T, 50), "#0f0");
  assert.equal(gauge(T, 75), "#fa0");
  assert.equal(gauge(T, 95), "#f00");
});

test("effort dots are cool, gold, then red at max", () => {
  assert.deepEqual(effort(T, { filled: 2, total: 5 }), { dots: "●●○○○", color: "#0ff" });
  assert.equal(effort(T, { filled: 4, total: 5 }).color, "#ff0");
  assert.equal(effort(T, { filled: 5, total: 5 }).color, "#f00");
  assert.equal(effort(T, null), null);
});

test("plain drops highlight braces", () => {
  assert.equal(plain("Fix {login} page"), "Fix login page");
});
