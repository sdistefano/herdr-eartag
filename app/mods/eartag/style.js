// Semantic states from `eartag.py json` -> theme colors and glyphs. Pure (takes the theme
// object), so it is testable with node --test. Colors are always theme names' values.

export const SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/** Rephrasing verdict tag -> [label, theme color name, short glyph]. */
export const VERDICTS = {
  DONE: ["✓ DONE", "done", "✓"],
  PARTIAL: ["◐ PARTIAL", "working", "◐"],
  FAILED: ["✗ FAILED", "blocked", "✗"],
  WAITING: ["? YOUR TURN", "blocked", "?"],
  WORKING: ["◐ WORKING", "working", "◐"],
};

/** Agent status -> [label, theme color name]. */
export const STATUSES = {
  working: ["WORKING", "working"],
  blocked: ["NEEDS YOU", "blocked"],
  done: ["DONE", "done"],
  idle: ["IDLE", "idle"],
  unknown: ["—", "dim"],
};

/** A role the Python side names (pad marks, activity) -> theme color name and weight. */
const ROLES = {
  accent: "accent",
  working: "working",
  blocked: "blocked",
  ok: "done",
  done: "done",
  text: "foreground",
  sub: "muted",
  dim: "dim",
};

/** "working b" -> { color, bold: true }; unknown roles read as plain text. */
export function role(t, name) {
  const [base, weight] = String(name ?? "text").split(" ");
  return { color: t[ROLES[base] ?? "foreground"], bold: weight === "b" };
}

export function verdict(t, tag) {
  const found = VERDICTS[tag];
  return found ? { label: found[0], color: t[found[1]], glyph: found[2] } : null;
}

export function status(t, name) {
  const [label, color] = STATUSES[name] ?? STATUSES.unknown;
  return { label, color: t[color] };
}

/** Gauge color, as the TUI's pct_role: red from 90 %, gold from 70 %. */
export function gauge(t, pct) {
  if (pct == null) return t.dim;
  if (pct >= 90) return t.blocked;
  if (pct >= 70) return t.working;
  return t.done;
}

/** Effort dots on the model's own scale: cool for low, gold for high, red for max. */
export function effort(t, level) {
  if (!level?.total) return null;
  const { filled, total } = level;
  const color = filled >= total ? t.blocked : filled / total >= 0.6 ? t.ansi3 : t.ansi6;
  return { dots: "●".repeat(filled) + "○".repeat(Math.max(0, total - filled)), color };
}

/** Rephrased text marks key words as {this}: the mod shows them plain. */
export const plain = (text) => String(text ?? "").replace(/[{}]/g, "");
