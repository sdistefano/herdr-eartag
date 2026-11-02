"""Colors: follow the herdr theme (config.toml [theme]) or the terminal's ANSI palette."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import herdr_config_path
from .palettes import PALETTES

# Named colors used by herdr's "terminal" theme -> SGR foreground codes.
_NAMED_FG = {
    "reset": 39, "black": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34,
    "magenta": 35, "cyan": 36, "gray": 37, "darkgray": 90, "lightred": 91,
    "lightgreen": 92, "lightyellow": 93, "lightblue": 94, "lightmagenta": 95,
    "lightcyan": 96, "white": 97,
}

_ALIASES = {
    "catppuccin-mocha": "catppuccin", "latte": "catppuccin-latte", "light": "catppuccin-latte",
    "tokyonight": "tokyo-night", "tokyo-day": "tokyo-night-day", "tokyonight-day": "tokyo-night-day",
    "gruvbox-dark": "gruvbox", "onedark": "one-dark", "onelight": "one-light",
    "solarized-dark": "solarized", "lotus": "kanagawa-lotus", "rosepine": "rose-pine",
    "rosepine-dawn": "rose-pine-dawn", "dawn": "rose-pine-dawn",
}

_CUSTOM_KEYS = {
    "accent", "panel_bg", "surface0", "surface1", "overlay0", "overlay1", "text",
    "green", "yellow", "red", "blue", "teal", "peach",
}


def read_herdr_theme(path: Optional[Path] = None) -> Tuple[str, Dict[str, str]]:
    """Minimal TOML reading of [theme] name and [theme.custom] overrides."""
    path = path or herdr_config_path()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "catppuccin", {}
    section = ""
    values: Dict[str, Dict[str, str]] = {"theme": {}, "theme.custom": {}}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip() if not re.search(r'"[^"]*#', line) else line.strip()
        if not line:
            continue
        header = re.match(r"^\[([^\[\]]+)\]$", line)
        if header:
            section = header.group(1).strip()
            continue
        if section in values:
            kv = re.match(r'^([A-Za-z0-9_]+)\s*=\s*(?:"([^"]*)"|(true|false))', line)
            if kv:
                values[section][kv.group(1)] = kv.group(2) if kv.group(2) is not None else kv.group(3)
    theme = values["theme"]
    name = theme.get("name") or "catppuccin"
    if theme.get("auto_switch") == "true" and theme.get("dark_name"):
        name = theme["dark_name"]
    name = name.lower().replace(" ", "-").replace("_", "-")
    name = _ALIASES.get(name, name)
    custom = {k: v for k, v in values["theme.custom"].items() if k in _CUSTOM_KEYS}
    return name, custom


def _hex(value: str) -> Optional[Tuple[int, int, int]]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        return None
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> str:
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def _luminance(rgb: Tuple[int, int, int]) -> float:
    def chan(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


class Theme:
    """Maps semantic roles to SGR sequences."""

    ROLES = {
        "text": "text", "sub": "overlay1", "dim": "line", "accent": "accent",
        "working": "yellow", "blocked": "red", "done": "teal", "idle": "green",
        "unknown": "overlay0", "ok": "teal", "warn": "yellow", "crit": "red",
        "track": "mid", "bg": "panel_bg", "rule": "line", "panel": "panel", "tip": "surface1",
    }

    def __init__(self, palette: Dict[str, str], paint_background: bool = True):
        self.palette = dict(palette)
        # Tones between surface1 and overlay0, like the mockups' rails (#403d52) and
        # separators (#524f67) on rose-pine. herdr's palette has no such middle tones.
        low, high = _hex(self.palette.get("surface1", "")), _hex(self.palette.get("overlay0", ""))
        if low and high:
            self.palette["mid"] = _mix(low, high, 0.35)
            self.palette["line"] = _mix(low, high, 0.6)
        else:
            self.palette["mid"] = self.palette["line"] = "darkgray"
        surface = self.palette.get("surface0", "")
        self.palette["panel"] = surface if paint_background and _hex(surface) else "reset"
        self.paint_background = self.palette["panel"] != "reset"

    @classmethod
    def load(cls, mode: str, background: bool = True) -> "Theme":
        if mode == "ansi":
            return cls(dict(PALETTES["terminal"]), background)
        name, custom = read_herdr_theme()
        palette = dict(PALETTES.get(name) or PALETTES["catppuccin"])
        palette.update(custom)
        return cls(palette, background)

    def _color(self, role: str) -> str:
        return self.palette.get(self.ROLES.get(role, role), "reset")

    def fg(self, role: str) -> str:
        value = self._color(role)
        rgb = _hex(value)
        if rgb:
            return "38;2;{};{};{}".format(*rgb)
        return str(_NAMED_FG.get(value.lower(), 39))

    def bg(self, role: str) -> str:
        value = self._color(role)
        rgb = _hex(value)
        if rgb:
            return "48;2;{};{};{}".format(*rgb)
        code = _NAMED_FG.get(value.lower(), 39)
        if code == 39:
            return "49"
        return str(code + 10)

    def on(self, role: str) -> str:
        """Readable foreground for text drawn on top of `role` as background."""
        rgb = _hex(self._color(role))
        if rgb is None:
            return "30"
        if _luminance(rgb) > 0.30:
            dark = _hex(self.palette.get("panel_bg", "")) or (0, 0, 0)
            if _luminance(dark) > 0.2:
                dark = (0, 0, 0)
            return "38;2;{};{};{}".format(*dark)
        light = _hex(self.palette.get("text", "")) or (255, 255, 255)
        if _luminance(light) < 0.5:
            light = (255, 255, 255)
        return "38;2;{};{};{}".format(*light)
