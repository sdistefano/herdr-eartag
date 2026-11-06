"""Scratch pad of the agent's herdr tab: find it, read its ` marks, open it in nvim.

A pad is a markdown file shared by the user and the agent, one per herdr tab, resolved by
the `scratch` tool (`scratch --path`). Sections are headings that carry a letter
(`## `s needed from Silvio`); a fenced glossary under `## marks` names the letters and
may point `a ("read this now") at another section (`` `a -> `s `` or `` `a -> `l:last ``).

Only reads here: the panel never writes a pad. Editing happens in nvim, started in the
panel's own pane by the TUI (see `nvim_argv`).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

RESOLVE_TTL = (
    30.0  # herdr may renumber tab ids after a close: resolve again now and then
)
TABBAR_LUA = Path(__file__).with_name("pad_tabbar.lua")
APP_LUA = Path(__file__).with_name(
    "pad_app.lua"
)  # the Herdr app panel's nvim: bare, one buffer
RELOAD_VIM = Path(os.path.expanduser("~")) / ".cache" / "herdr-scratch" / "reload.vim"

_HEADING_RE = re.compile(r"^#{2,6}\s+`([a-z])\b\s*(.*)$")
_GLOSSARY_RE = re.compile(r"^`([a-z])\s+(.*)$")
_POINTER_RE = re.compile(r"^->\s*`([a-z])(:last)?")
_BOX_RE = re.compile(r"^\s*[-*] \[([ x/?!-])\]")
PLACEHOLDER = "- [ ] …"  # what `scratch` seeds an empty list with: not a task


@dataclass
class Section:
    letter: str
    title: str
    line: int  # 1-based line of the heading
    end: int  # last line of the section (1-based, inclusive)
    filled: bool  # holds something besides blank lines and the `- [ ] …` placeholder


@dataclass
class Pad:
    path: Path
    name: str
    sections: List[Section] = field(default_factory=list)
    glossary: Dict[str, str] = field(default_factory=dict)
    boxes: Dict[str, int] = field(default_factory=dict)  # checkbox state char -> count
    read_now: Optional[int] = None  # line `a points at

    @property
    def todo(self) -> Optional[Tuple[int, int]]:
        """(done, total) over the checkboxes; dropped items leave the denominator."""
        total = sum(n for state, n in self.boxes.items() if state != "-")
        return (self.boxes.get("x", 0), total) if total else None

    def line_of(self, letter: str) -> Optional[int]:
        """Line nvim opens at for a mark: `a follows its pointer, others their heading."""
        if letter == "a" and self.read_now:
            return self.read_now
        found = next((s for s in self.sections if s.letter == letter), None)
        return found.line if found else None


def parse(text: str, path: Path, name: str = "") -> Pad:
    """Read the sections, glossary, checkbox counts and the `a pointer of a pad."""
    lines = text.split("\n")
    pad = Pad(path=path, name=name or path.stem)
    pad.glossary = _glossary(lines)
    pad.sections = _sections(lines)
    for line in lines:
        m = _BOX_RE.match(line)
        if m and line.strip() != PLACEHOLDER:
            pad.boxes[m.group(1)] = pad.boxes.get(m.group(1), 0) + 1
    pad.read_now = _read_now(pad)
    return pad


def _glossary(lines: List[str]) -> Dict[str, str]:
    """Letters of the fenced block under `## marks`: {letter: meaning}."""
    out: Dict[str, str] = {}
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().lower() == "## marks")
    except StopIteration:
        return out
    fence = 0
    for line in lines[start + 1 :]:
        if line.startswith("```"):
            fence += 1
            if fence == 2:
                break
            continue
        if line.startswith("#"):
            break
        m = _GLOSSARY_RE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _sections(lines: List[str]) -> List[Section]:
    heads = [
        (i, m) for i, m in ((i, _HEADING_RE.match(l)) for i, l in enumerate(lines)) if m
    ]
    out: List[Section] = []
    for n, (i, m) in enumerate(heads):
        end = heads[n + 1][0] - 1 if n + 1 < len(heads) else len(lines) - 1
        while end > i and not lines[end].strip():
            end -= 1
        body = [l.strip() for l in lines[i + 1 : end + 1]]
        filled = any(l and l not in (PLACEHOLDER, "…") for l in body)
        out.append(Section(m.group(1), m.group(2).strip(), i + 1, end + 1, filled))
    return out


def _read_now(pad: Pad) -> Optional[int]:
    """`a -> `s opens at the `s heading; `a -> `l:last at that section's last line."""
    m = _POINTER_RE.match(pad.glossary.get("a", ""))
    if not m:
        own = next((s for s in pad.sections if s.letter == "a"), None)
        return own.line if own else None
    target = next((s for s in pad.sections if s.letter == m.group(1)), None)
    if not target:
        return None
    return target.end if m.group(2) else target.line


class PadWatcher:
    """Resolves the pad of the agent pane's tab and re-parses it when the file changes."""

    def __init__(
        self,
        resolver: Optional[Callable[[dict], Optional[Path]]] = None,
        available: Optional[bool] = None,
    ) -> None:
        # resolver: pane dict -> pad path (the herdr TUI's `resolve` by default; the
        # herdr-core source asks `scratch` as that terminal instead).
        self.resolver = resolver or resolve
        self.available = (
            shutil.which("scratch") is not None if available is None else available
        )
        self.pad: Optional[Pad] = None
        self._path: Optional[Path] = None
        self._key: Tuple[str, str] = ("", "")
        self._resolved_at = 0.0
        self._mtime = 0.0

    def refresh(self, pane: Optional[dict], now: Optional[float] = None) -> bool:
        """True when the pad (or which pad) changed since the last call."""
        if not self.available or not pane:
            return False
        now = now or time.time()
        key = (str(pane.get("tab_id") or ""), str(pane.get("workspace_id") or ""))
        if key != self._key or now - self._resolved_at > RESOLVE_TTL:
            self._key, self._resolved_at = key, now
            path = self.resolver(pane)
            if path != self._path:
                self._path, self._mtime = path, 0.0
                if path is None and self.pad is not None:
                    self.pad = None
                    return True
        if self._path is None:
            return False
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            changed, self.pad = self.pad is not None, None
            return changed
        if mtime == self._mtime:
            return False
        self._mtime = mtime
        try:
            text = self._path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        self.pad = parse(text, self._path)
        return True


def resolve(pane: dict) -> Optional[Path]:
    """Ask `scratch --path` for the pad of the pane's tab, as if run inside that pane."""
    env = dict(os.environ)
    env.update(
        {
            "HERDR_PANE_ID": str(pane.get("pane_id") or ""),
            "HERDR_TAB_ID": str(pane.get("tab_id") or ""),
            "HERDR_WORKSPACE_ID": str(pane.get("workspace_id") or ""),
        }
    )
    try:
        proc = subprocess.run(
            ["scratch", "--path"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = proc.stdout.strip()
    return Path(out) if proc.returncode == 0 and out else None


def nvim_argv(
    path: Path, line: Optional[int], tabbar: bool = True, listen: Optional[str] = None
) -> List[str]:
    """nvim on the pad with the same live reload and keys as the scratch pane, plus the
    panel's tab bar (the TUI; the Herdr app draws its own); `+line` puts the cursor on the
    mark that was clicked; `listen`: a socket the app drives it through (mark jumps)."""
    argv = ["nvim"]
    if not tabbar:
        # The app's nvim shares the pad with the tab's scratch pane: no swap file of its
        # own, and no W325 "ignoring swapfile" prompt on every open (set before the file loads).
        argv += ["-n", "--cmd", "set shortmess+=A"]
    if listen:
        argv += ["--listen", listen]
    if RELOAD_VIM.exists():
        argv += ["-S", str(RELOAD_VIM)]
    argv += ["-S", str(TABBAR_LUA if tabbar else APP_LUA)]
    if line:
        argv.append("+{}".format(line))
    return argv + [str(path)]


def chips(pad: Pad) -> List[Tuple[str, str, str, str]]:
    """Marks list of the recap, as (letter, title, count, role): `a first, then sections in
    file order. The title is the section heading, else the glossary's meaning of the letter.

    `s lights up when something waits on the user (the section has content, or items are
    `[?]`), `t carries done/total, empty sections are dimmed.
    """
    out: List[Tuple[str, str, str, str]] = []
    if pad.read_now:
        out.append(("a", _read_now_title(pad), "", "accent b"))
    waiting = pad.boxes.get("?", 0)
    seen = {"a"} if pad.read_now else set()
    for sec in pad.sections:
        if sec.letter in seen:
            continue
        seen.add(sec.letter)
        title = sec.title or pad.glossary.get(sec.letter, "")
        out.append((sec.letter, title) + _chip(sec, pad, waiting))
    return out


def _read_now_title(pad: Pad) -> str:
    """`a -> `l:last   read this now  ->  "read this now · `l"."""
    meaning = pad.glossary.get("a", "")
    m = _POINTER_RE.match(meaning)
    if not m:
        return meaning or "read this now"
    rest = meaning[m.end() :].strip() or "read this now"
    return "{} · `{}".format(rest, m.group(1))


def _chip(sec: Section, pad: Pad, waiting: int) -> Tuple[str, str]:
    """Count and role of one section's line."""
    if sec.letter == "s":
        hot = sec.filled or waiting
        return (str(waiting) if waiting else "", "working b" if hot else "dim")
    if sec.letter == "t" and pad.todo:
        done, total = pad.todo
        return ("{}/{}".format(done, total), "ok" if done == total else "text")
    return ("", "text" if sec.filled else "dim")
