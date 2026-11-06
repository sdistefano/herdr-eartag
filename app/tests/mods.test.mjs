// node --test app/tests: the pure parts of the Herdr app mods (no herdr runtime needed).
import { test } from "node:test";
import assert from "node:assert/strict";
import { newPanel, ownerOf, plan, prune, splitAddress } from "../mods/eartag-key/toggle.js";
import { effort, gauge, plain, role, status, verdict } from "../mods/eartag/style.js";

const agentPane = { pane: "pa", terminal: "box/t2", tab: "tb1" };
const panelPane = { pane: "pp", terminal: null, mod: "eartag", tab: "tb1" };
const otherPane = { pane: "pb", terminal: "box/t18", tab: "tb2" };

test("opens a panel for an agent pane without one", () => {
  const step = plan({ pane: "pa", terminal: "box/t2" }, [agentPane], {});
  assert.deepEqual(step, { kind: "open", pane: "pa", terminal: "box/t2" });
});

test("closes the agent's live panel", () => {
  const step = plan({ pane: "pa", terminal: "box/t2" }, [agentPane, panelPane], { "box/t2": "pp" });
  assert.deepEqual(step, { kind: "close", pane: "pp", terminal: "box/t2" });
});

test("pressed inside the panel closes that panel", () => {
  const step = plan({ pane: "pp", terminal: null }, [agentPane, panelPane], { "box/t2": "pp" });
  assert.deepEqual(step, { kind: "close", pane: "pp", terminal: "box/t2" });
});

test("a second agent gets its own panel, not the first's", () => {
  const step = plan({ pane: "pb", terminal: "box/t18" }, [agentPane, panelPane, otherPane], { "box/t2": "pp" });
  assert.deepEqual(step, { kind: "open", pane: "pb", terminal: "box/t18" });
});

test("a registry entry whose panel is gone reopens", () => {
  const step = plan({ pane: "pa", terminal: "box/t2" }, [agentPane], { "box/t2": "pp" });
  assert.equal(step.kind, "open");
});

test("nothing focused does nothing", () => {
  assert.deepEqual(plan(null, [], {}), { kind: "none" });
});

test("newPanel finds the split eartag pane in the tab", () => {
  assert.equal(newPanel([agentPane], [agentPane, panelPane], "tb1"), "pp");
  assert.equal(newPanel([agentPane, panelPane], [agentPane, panelPane], "tb1"), null);
});

test("prune drops closed panels; ownerOf finds the terminal", () => {
  assert.deepEqual(prune({ "box/t2": "pp", "box/t18": "gone" }, [panelPane]), { "box/t2": "pp" });
  assert.deepEqual(ownerOf({ "box/t2": "pp" }, "pp"), ["box/t2", "pp"]);
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
