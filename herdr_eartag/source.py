"""Where the panel gets its pane facts: the herdr TUI, or a herdr-core terminal.

`PanelModel` reads a pane dict shaped like `herdr pane get` (agent, agent_status,
agent_session, cwd, foreground_cwd, pane_id, tab_id, workspace_id), the agent list, and
the pane's scratch pad path. A source supplies those three things:

- `HerdrSource`: the herdr TUI (the plugin's panel), through `herdr.py`.
- `CoreSource`: a herdr-core terminal (`t18`), as the Herdr app shows it. There is no
  `herdr pane get` there; the same facts come from `hc get tN --json` and Claude Code's
  `~/.claude/sessions/<pid>.json` (pid of the terminal's foreground program).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import herdr, pad
from .config import claude_dir

# (argv, env) -> (exit code, stdout)
Runner = Callable[..., Tuple[int, str]]

# The agent's own report (OSC 7501 `app`) -> the agent name the panel knows.
APP_AGENTS = {"claude-code": "claude", "claude": "claude", "codex": "codex"}
# The foreground process name, when the agent reported nothing (yet).
PROCESS_AGENTS = {"claude": "claude", "codex": "codex"}
NO_PAD = 3  # `scratch --path` exit code when no pad resolves
HC_TIMEOUT = 5.0


def tool_path() -> str:
    """PATH with the box's own bin folders first: `hc` lives in ~/.local/bin and
    `scratch` in ~/.bin, which a non-interactive shell (herdr-core's exec) may lack."""
    home = Path.home()
    extra = [str(home / ".local" / "bin"), str(home / ".bin")]
    current = [
        p for p in os.environ.get("PATH", "").split(os.pathsep) if p and p not in extra
    ]
    return os.pathsep.join(extra + current)


def run_tool(argv: List[str], env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    """Run a box tool with the extended PATH; (exit code, stdout)."""
    full_env = dict(os.environ, PATH=tool_path())
    full_env.update(env or {})
    proc = subprocess.run(
        argv,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=HC_TIMEOUT,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout


class HerdrSource:
    """The herdr TUI: what the plugin's panel has always used."""

    def pane(self, target: str) -> Optional[Dict[str, Any]]:
        return herdr.pane_get(target)

    def agents(self) -> List[Dict[str, Any]]:
        return herdr.agent_list()

    def pad_path(self, pane: dict) -> Optional[Path]:
        return pad.resolve(pane)

    def scratch_available(self) -> bool:
        return shutil.which("scratch") is not None


class CoreSource:
    """A herdr-core terminal, read with `hc` and Claude Code's session files."""

    def __init__(self, run: Runner = run_tool, sessions_dir: Optional[Path] = None):
        self.run = run
        self.sessions_dir = sessions_dir or claude_dir() / "sessions"

    # -- source interface ---------------------------------------------------------
    def pane(self, terminal: str) -> Optional[Dict[str, Any]]:
        """The pane dict for `terminal`, or None when herdr-core has no such terminal."""
        term = self._hc_json(["hc", "get", terminal, "--json"])
        return self.to_pane(term) if isinstance(term, dict) else None

    def agents(self) -> List[Dict[str, Any]]:
        """Every terminal running an agent, as pane dicts (for the same-branch alert)."""
        terms = self._hc_json(["hc", "ls", "--json"])
        panes = (
            [self.to_pane(t) for t in terms if isinstance(t, dict)]
            if isinstance(terms, list)
            else []
        )
        return [p for p in panes if p["agent"]]

    def pad_path(self, pane: dict) -> Optional[Path]:
        """`scratch --path` as if run in that terminal. SCRATCH_GUARD=off: the pad is bound
        to the agent's session, not ours, and we only read it."""
        env = {"HC_TERMINAL_ID": str(pane.get("pane_id") or ""), "SCRATCH_GUARD": "off"}
        try:
            code, out = self.run(["scratch", "--path"], env=env)
        except (OSError, subprocess.SubprocessError):
            return None
        out = out.strip()
        return Path(out) if code == 0 and out else None

    def start_pad(self, pane: dict, session_id: Optional[str]) -> Optional[Path]:
        """Create the terminal's pad when it has none, without opening a pane (the app
        shows its own nvim). With the agent's session id this is what the SessionStart hook
        does (`scratch --set-session`: line 1 binds the pad to that session); without one,
        `scratch --seed`. Returns the pad path, or None when no pad can resolve (exit 3:
        the terminal has no `where` label yet)."""
        env = {"HC_TERMINAL_ID": str(pane.get("pane_id") or ""), "SCRATCH_GUARD": "off"}
        argv = (
            ["scratch", "--set-session", session_id]
            if session_id
            else ["scratch", "--seed"]
        )
        try:
            code, _ = self.run(argv, env=env)
        except (OSError, subprocess.SubprocessError):
            return None
        return self.pad_path(pane) if code == 0 else None

    def scratch_available(self) -> bool:
        return shutil.which("scratch", path=tool_path()) is not None

    # -- translation --------------------------------------------------------------
    def to_pane(self, term: Dict[str, Any]) -> Dict[str, Any]:
        """`hc get --json` -> the `herdr pane get` fields PanelModel reads."""
        fg = term.get("foreground") if isinstance(term.get("foreground"), dict) else {}
        status = term.get("status") if isinstance(term.get("status"), dict) else {}
        labels = term.get("labels") if isinstance(term.get("labels"), dict) else {}
        agent = APP_AGENTS.get(str(status.get("app") or "")) or PROCESS_AGENTS.get(
            str(fg.get("name") or ""), ""
        )
        session = self._session(fg.get("pid")) if agent == "claude" else {}
        return {
            "pane_id": term.get("address"),
            "agent": agent,
            "agent_status": status.get("state") or ("idle" if agent else None),
            "agent_session": (
                {"value": session["sessionId"]} if session.get("sessionId") else None
            ),
            "cwd": term.get("cwd"),
            "foreground_cwd": fg.get("cwd") or session.get("cwd"),
            "tab_id": labels.get("herdr.tab"),
            "workspace_id": labels.get("herdr.space"),
        }

    def _session(self, pid: Any) -> Dict[str, Any]:
        """Claude Code's ~/.claude/sessions/<pid>.json, or {}."""
        if not isinstance(pid, int):
            return {}
        try:
            with open(
                self.sessions_dir / "{}.json".format(pid), encoding="utf-8"
            ) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _hc_json(self, argv: List[str]) -> Any:
        """Parsed JSON from an hc command; None when it fails (no such terminal).
        Raises HerdrError when hc itself cannot run (herdr-core unreachable)."""
        try:
            code, out = self.run(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            raise herdr.HerdrError("core_unreachable", str(exc))
        if code != 0:
            return None
        try:
            return json.loads(out)
        except ValueError:
            return None
