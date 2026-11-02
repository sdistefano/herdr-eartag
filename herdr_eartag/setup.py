"""One-click setup: Claude Code statusline relay (quotas) and the prefix+i key.

Both steps are idempotent, keep a backup of the file they edit, and can be undone.
They run only when the user asks: the `setup` action, or the "Enable" line / menu
entry in the panel.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from . import herdr, statusline
from .config import claude_dir, data_dir, ensure_private_dir, herdr_config_path

PLUGIN_ID = "thomashuangth.eartag"
KEY = "prefix+i"
_BEGIN = "# eartag:begin"
_END = "# eartag:end"


def plugin_id() -> str:
    return os.environ.get("HERDR_PLUGIN_ID") or PLUGIN_ID


# -- statusline relay ---------------------------------------------------------------
def _settings_path() -> Path:
    return claude_dir() / "settings.json"


def _previous_path() -> Path:
    return data_dir() / "statusline" / "previous.json"


def tap_install_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / "herdr-eartag" / "statusline_tap.py"


def _load_settings() -> Optional[dict]:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".settings.", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    try:
        os.chmod(tmp, os.stat(path).st_mode & 0o777 if path.exists() else 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def statusline_installed() -> bool:
    settings = _load_settings() or {}
    current = settings.get("statusLine")
    return isinstance(current, dict) and "statusline_tap.py" in str(current.get("command", ""))


def install_statusline() -> str:
    settings = _load_settings()
    path = _settings_path()
    if settings is None:
        return "Statusline: cannot read {}, nothing changed.".format(path)
    tap = tap_install_path()
    ensure_private_dir(tap.parent)
    shutil.copyfile(Path(statusline.__file__), tap)
    os.chmod(tap, 0o700)
    if statusline_installed():
        return "Statusline: relay already installed (refreshed)."
    current = settings.get("statusLine")
    previous = _previous_path()
    ensure_private_dir(previous.parent)
    previous.write_text(json.dumps({"statusLine": current}), encoding="utf-8")
    os.chmod(previous, 0o600)
    backup = path.with_name(path.name + ".herdr-eartag.bak")
    if path.exists() and not backup.exists():
        shutil.copyfile(path, backup)
    command = "{} {}".format(shlex.quote(sys.executable or "python3"), shlex.quote(str(tap)))
    new = dict(current) if isinstance(current, dict) else {"type": "command"}
    if isinstance(current, dict) and current.get("type") == "command" and current.get("command"):
        command += " --then " + shlex.quote(str(current["command"]))
    new["type"] = "command"
    new["command"] = command
    settings["statusLine"] = new
    _write_json_atomic(path, settings)
    kept = " Your statusline still runs as before." if isinstance(current, dict) and current.get("command") else ""
    return "Statusline: relay added to {}.{}".format(path, kept)


def remove_statusline() -> str:
    settings = _load_settings()
    if settings is None or not statusline_installed():
        return "Statusline: relay not installed."
    try:
        previous = json.loads(_previous_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {"statusLine": None}
    if previous.get("statusLine"):
        settings["statusLine"] = previous["statusLine"]
    else:
        settings.pop("statusLine", None)
    _write_json_atomic(_settings_path(), settings)
    return "Statusline: previous statusline restored."


# -- keybinding ---------------------------------------------------------------------
def _config_text() -> str:
    try:
        return herdr_config_path().read_text(encoding="utf-8")
    except OSError:
        return ""


def keybinding_state() -> str:
    """installed | conflict (prefix+i used by something else) | missing"""
    text = _config_text()
    if "{}.toggle".format(plugin_id()) in text:
        return "installed"
    if re.search(r'["\']{}["\']'.format(re.escape(KEY)), text):
        return "conflict"
    return "missing"


def install_keybinding() -> str:
    state = keybinding_state()
    if state == "installed":
        return "Key: {} already set.".format(KEY)
    if state == "conflict":
        return "Key: {} is already used in {}; bind {}.toggle yourself.".format(KEY, herdr_config_path(), plugin_id())
    path = herdr_config_path()
    text = _config_text()
    if path.exists():
        backup = path.with_name(path.name + ".herdr-eartag.bak")
        if not backup.exists():
            shutil.copyfile(path, backup)
    block = (
        "\n{begin} (added by the Eartag plugin; remove this block to unbind)\n"
        "[[keys.command]]\n"
        'key = "{key}"\n'
        'type = "plugin_action"\n'
        'command = "{pid}.toggle"\n'
        'description = "eartag panel"\n'
        "{end}\n"
    ).format(begin=_BEGIN, end=_END, key=KEY, pid=plugin_id())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(("" if not text or text.endswith("\n") else "\n") + block)
    _reload_herdr()
    return "Key: {} now shows or hides the panel.".format(KEY)


def remove_keybinding() -> str:
    text = _config_text()
    pattern = re.compile(r"\n?{}.*?{}\n?".format(re.escape(_BEGIN), re.escape(_END)), re.S)
    if not pattern.search(text):
        return "Key: nothing added by Eartag."
    herdr_config_path().write_text(pattern.sub("\n", text).rstrip("\n") + "\n", encoding="utf-8")
    _reload_herdr()
    return "Key: {} removed.".format(KEY)


def _reload_herdr() -> None:
    try:
        herdr.call("server", "reload-config")
    except herdr.HerdrError:
        pass


# -- all -----------------------------------------------------------------------------
def needs_setup() -> bool:
    return not statusline_installed() or keybinding_state() == "missing"


def run_all() -> List[str]:
    return [install_statusline(), install_keybinding()]


def undo_all() -> List[str]:
    return [remove_statusline(), remove_keybinding()]
