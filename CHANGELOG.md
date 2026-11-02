# Changelog

## 0.1.0

First public release.

- Panel on the right of every agent pane, opened automatically, toggled with
  `prefix+i`, hidden per agent or per workspace from the `⋯` menu.
- Recap of the current ask, the tool running, task progress, and what the agent
  did under a colored verdict (done, partial, failed, waiting for you, working).
- History of the three previous asks with their outcome, edited files with the
  repository's uncommitted `+added −removed` lines, ask duration, alerts.
- Context, 5-hour and 7-day quota gauges through an optional Claude Code
  statusline relay, with reset times on hover.
- Model and effort on each family's own scale (Claude, OpenAI/Codex, Gemini, Grok).
- Optional rephrasing with your own `claude`, `codex` or `gemini` CLI, off by
  default, with no tools, MCP servers or hooks.
- Follows the herdr theme; English and French; ASCII mode.
