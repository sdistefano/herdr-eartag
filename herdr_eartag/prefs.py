"""Small persistent preferences: hidden panes/workspaces, auto-open, rephrasing,
and the registry mapping agent panes to their eartag panel."""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .config import ensure_private_dir, state_dir

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows is not supported by the manifest
    fcntl = None  # type: ignore


def _path() -> Path:
    return state_dir() / "prefs.json"


def _empty() -> Dict[str, Any]:
    return {
        "auto_open": None,  # None = follow config
        "summarize": None,  # None = follow config, True/False = chosen from the menu
        "hidden_panes": {},
        "hidden_workspaces": {},
        "panels": {},  # agent pane id -> panel pane id
        "pids": {},    # panel pane id -> panel process id (detects ghosts after a restart)
    }


def load() -> Dict[str, Any]:
    data = _empty()
    try:
        with open(_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            for key in data:
                if key in raw and isinstance(raw[key], type(data[key])) or (key in ("auto_open", "summarize") and key in raw):
                    data[key] = raw[key]
    except (OSError, ValueError):
        pass
    return data


def save(data: Dict[str, Any]) -> None:
    directory = ensure_private_dir(state_dir())
    fd, tmp = tempfile.mkstemp(prefix=".prefs.", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, _path())
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked() -> Iterator[Dict[str, Any]]:
    """Read-modify-write the prefs under an exclusive lock."""
    directory = ensure_private_dir(state_dir())
    lock_path = directory / ".lock"
    with open(lock_path, "a") as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = load()
            yield data
            save(data)
        finally:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)


def auto_open_enabled(data: Dict[str, Any], config_default: bool) -> bool:
    value = data.get("auto_open")
    return config_default if value is None else bool(value)


def is_hidden(data: Dict[str, Any], pane_id: str, workspace_id: Optional[str]) -> bool:
    if pane_id in data.get("hidden_panes", {}):
        return True
    return bool(workspace_id and workspace_id in data.get("hidden_workspaces", {}))


def summarize_enabled(data: Dict[str, Any]) -> bool:
    """False when the user paused rephrasing from the panel menu."""
    return data.get("summarize") is not False


def summarize_wanted(data: Dict[str, Any], config_value: str) -> bool:
    """Menu choice (True/False) wins over the config file; None follows the config."""
    choice = data.get("summarize")
    if choice is None:
        return config_value != "off"
    return bool(choice)
