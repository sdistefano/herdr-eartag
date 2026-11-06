"""`eartag.py json`: the panel's view model as one JSON document, for the Herdr app mod.

The TUI draws a `render.View` with ANSI; the app mod draws the same facts with its own
theme. So this sends data and semantic states (status, verdict, roles such as
`working b` or `dim`), never colors or escape codes.

Rephrasing is slow (an LLM call per ask). Each `json` run is a short process, so it
never waits for one: it returns what the summary cache holds, claims what is missing
(a claim file other runs respect), and a detached child fills the cache after the
document is printed, for a later run to pick up.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import pad as padmod
from .config import ensure_private_dir, state_dir
from .render import View
from .summarize import Summarizer

SCHEMA = 1
CLAIM_TTL = (
    120.0  # a claim older than this was left by a warmer that died: take it over
)

# View fields that only make sense for the ANSI renderer (or that pad_data carries).
TUI_ONLY = (
    "width",
    "height",
    "ascii",
    "menu",
    "menu_index",
    "hover_mark",
    "selected_bar",
    "marks",
    "pad_name",
)


def _pair(names: Tuple[str, ...]) -> Callable[[Any], Optional[Dict[str, Any]]]:
    """Tuple -> dict with those keys (None stays None)."""
    return lambda value: dict(zip(names, value)) if value else None


# Tuple-shaped View fields, turned into named objects for the mod.
CONVERTERS: Dict[str, Callable[[Any], Any]] = {
    "notif": _pair(("text", "role")),
    "diff": _pair(("added", "removed")),
    "effort_level": _pair(("filled", "total")),
    "before": lambda rows: [dict(zip(("time", "title", "verdict"), r)) for r in rows],
}


def view_data(v: View) -> Dict[str, Any]:
    """The View as plain data: tuples become named objects, TUI-only fields go."""
    raw = dataclasses.asdict(v)
    data = {
        k: CONVERTERS.get(k, lambda x: x)(val)
        for k, val in raw.items()
        if k not in TUI_ONLY
    }
    tasks = v.tasks
    data["tasks"] = (
        {"done": tasks[0], "total": tasks[1], "now": v.task_now} if tasks else None
    )
    return data


def pad_data(pad: Optional[padmod.Pad]) -> Optional[Dict[str, Any]]:
    """The pad's marks (one clickable line each, with the line nvim opens at), its
    sections, glossary, checkbox counts and the `a pointer; None without a pad."""
    if pad is None:
        return None
    todo = pad.todo
    return {
        "path": str(pad.path),
        "name": pad.name,
        "marks": [
            {
                "letter": letter,
                "title": title,
                "count": count,
                "role": role,
                "line": pad.line_of(letter),
            }
            for letter, title, count, role in padmod.chips(pad)
        ],
        "sections": [
            {"letter": s.letter, "title": s.title, "line": s.line, "filled": s.filled}
            for s in pad.sections
        ],
        "glossary": pad.glossary,
        "todo": {"done": todo[0], "total": todo[1]} if todo else None,
        "read_now": pad.read_now,
    }


def document(
    terminal: str,
    session_id: Optional[str],
    v: View,
    pad: Optional[padmod.Pad],
    error: str,
) -> Dict[str, Any]:
    """The whole answer of `eartag.py json --terminal tN`."""
    return {
        "schema": SCHEMA,
        "terminal": terminal,
        "session_id": session_id,
        "error": error,
        "ts": time.time(),
        "view": view_data(v),
        "pad": pad_data(pad),
    }


class CachedSummarizer(Summarizer):
    """A Summarizer for one-shot runs: cache hits only, misses are claimed for `warm`."""

    def __init__(self, setting: str = "off", model: str = ""):
        super().__init__(setting, model)
        self._claims = state_dir() / "summaries.claims"
        self.todo: List[Tuple[str, str, str, int]] = (
            []
        )  # (key, kind, text, width) we claimed

    def claim_path(self, key: str) -> Path:
        return self._claims / key

    def get(self, kind: str, text: str, width: int) -> Optional[str]:
        """Cached summary, or None; a miss is claimed (once across runs) for `warm`."""
        if not self.available or not text.strip():
            return None
        key = self._key(kind, text, width)
        if key in self._cache:
            return self._cache[key]
        if self._claim(key):
            self.todo.append((key, kind, text, width))
        return None

    def pending(self, kind: str, text: str, width: int) -> bool:
        key = self._key(kind, text, width)
        return key not in self._cache and self._fresh(self.claim_path(key))

    def _fresh(self, path: Path) -> bool:
        try:
            return time.time() - path.stat().st_mtime < CLAIM_TTL
        except OSError:
            return False

    def _claim(self, key: str) -> bool:
        """Create the claim file; False when another live run holds it."""
        path = self.claim_path(key)
        ensure_private_dir(path.parent)
        if path.exists() and not self._fresh(path):
            path.unlink(missing_ok=True)
        try:
            os.close(os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            return True
        except FileExistsError:
            return False

    def warm(self) -> None:
        """Fill the cache for every claimed miss (blocking), then drop the claims."""
        for key, kind, text, width in self.todo:
            try:
                self._run(key, kind, text, width)
            finally:
                self.claim_path(key).unlink(missing_ok=True)


def warm_detached(summarizer: Optional[CachedSummarizer]) -> None:
    """Run `summarizer.warm()` in a detached child, so the caller can exit at once.
    The child leaves our session and closes stdout, so `exec` stops waiting for it."""
    if summarizer is None or not summarizer.todo or not hasattr(os, "fork"):
        return
    sys.stdout.flush()
    if os.fork() != 0:
        return
    try:
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        summarizer.warm()
    finally:
        os._exit(0)
