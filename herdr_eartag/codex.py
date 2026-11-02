"""Model and reasoning effort of a Codex session (~/.codex/sessions/**/rollout-*.jsonl).

Codex writes a `turn_context` record per turn with `model` and `effort`. Only the
file tail is read. Asks and history are not read for Codex yet.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional, Tuple

TAIL = 512 * 1024
_cache = {}


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex"))


def _sessions() -> list:
    base = codex_home() / "sessions"
    try:
        files = list(base.glob("*/*/*/rollout-*.jsonl"))
    except OSError:
        return []
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _session_cwd(path: Path) -> Optional[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            first = json.loads(fh.readline() or "{}")
    except (OSError, ValueError):
        return None
    payload = first.get("payload") if isinstance(first, dict) else None
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    return cwd if isinstance(cwd, str) else None


def find_session(session_id: Optional[str], cwd: Optional[str]) -> Optional[Path]:
    files = _sessions()
    if session_id and re.fullmatch(r"[A-Za-z0-9-]+", session_id):
        for path in files:
            if path.name.endswith("{}.jsonl".format(session_id)):
                return path
    if cwd:
        for path in files[:60]:
            if _session_cwd(path) == cwd:
                return path
    return None


def model_and_effort(path: Path) -> Tuple[str, str]:
    """Latest (model, effort) from the session's turn_context records."""
    try:
        stat = path.stat()
    except OSError:
        return "", ""
    key = (str(path), stat.st_size, stat.st_mtime)
    if key in _cache:
        return _cache[key]
    model = effort = ""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, stat.st_size - TAIL))
            lines = fh.read().splitlines()
    except OSError:
        return "", ""
    for raw in reversed(lines):
        if b'"turn_context"' not in raw:
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        payload = obj.get("payload") if isinstance(obj, dict) else None
        if isinstance(payload, dict):
            model = str(payload.get("model") or "")
            effort = str(payload.get("effort") or payload.get("reasoning_effort") or "")
            break
    _cache.clear()
    _cache[key] = (model, effort)
    return model, effort


def configured() -> Tuple[str, str]:
    """Fallback from ~/.codex/config.toml (model, model_reasoning_effort)."""
    try:
        text = (codex_home() / "config.toml").read_text(encoding="utf-8")
    except OSError:
        return "", ""
    def value(key: str) -> str:
        m = re.search(r'^\s*{}\s*=\s*"([^"]*)"'.format(key), text, re.M)
        return m.group(1) if m else ""
    return value("model"), value("model_reasoning_effort")
