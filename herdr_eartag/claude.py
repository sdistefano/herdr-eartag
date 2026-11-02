"""Incremental reader for Claude Code session transcripts (~/.claude/projects/*/<id>.jsonl).

Transcripts can weigh tens of MB, so only the tail is read on first load, then
only appended bytes on each refresh.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import claude_dir

INITIAL_TAIL = 4 * 1024 * 1024
BACKFILL_CHUNK = 8 * 1024 * 1024
BACKFILL_LIMIT = 48 * 1024 * 1024
MAX_READ_PER_REFRESH = 16 * 1024 * 1024
WANTED_ASKS = 4
KEEP_ASKS = 12

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read"}

_SKIP_PREFIXES = (
    "<",
    "Another Claude session",
    "This session is being continued",
    "[Request interrupted",
    "Caveat:",
    "[Artifact comment",
)
# Claude Code's own slash commands: settings and housekeeping, never a task.
BUILTIN_COMMANDS = {
    "add-dir", "agents", "bashes", "bug", "clear", "compact", "config", "context", "cost",
    "doctor", "effort", "exit", "export", "fast", "feedback", "help", "hooks", "ide", "init",
    "install-github-app", "keybindings", "login", "logout", "mcp", "memory", "model",
    "output-style", "permissions", "plugin", "plugins", "privacy-settings", "release-notes",
    "resume", "rewind", "sandbox", "skills", "status", "statusline", "terminal-setup", "theme",
    "todos", "upgrade", "usage", "vim", "quit", "loop", "remote", "tasks",
}
_COMMAND_RE = re.compile(r"<command-name>\s*(/?[^<\s]+)\s*</command-name>")
_COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.S)
_PASTED_RE = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)
_IMAGE_RE = re.compile(r"\[Image #\d+\]")


def encode_project_dir(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def parse_ts(value) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def clean_prompt(text: str) -> Optional[str]:
    """Return the user's ask as displayable text, or None for system-injected turns."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    cmd = _COMMAND_RE.search(text)
    if cmd:
        name = cmd.group(1)
        if not name.startswith("/"):
            name = "/" + name
        if name[1:].split(":")[-1].lower() in BUILTIN_COMMANDS:
            return None  # session housekeeping, not an ask
        args = _COMMAND_ARGS_RE.search(text)
        arg_text = args.group(1).strip() if args else ""
        return (name + " " + arg_text).strip()
    if text.startswith(_SKIP_PREFIXES):
        return None
    text = _PASTED_RE.sub("[…]", text)
    text = _IMAGE_RE.sub("", text).strip()
    return text or None


def prompt_from_record(obj: dict) -> Optional[str]:
    if obj.get("type") != "user" or obj.get("isMeta") or obj.get("isSidechain"):
        return None
    if "toolUseResult" in obj:
        return None
    message = obj.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return clean_prompt(content)
    if isinstance(content, list):
        texts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                return None
            if block.get("type") == "text":
                texts.append(block.get("text") or "")
        return clean_prompt("\n".join(texts)) if texts else None
    return None


def tool_label(name: str, params: dict) -> str:
    """Short, non-sensitive label for a tool call: file basenames and program names only."""
    if name.startswith("mcp__"):
        name = name.rsplit("__", 1)[-1]
    if not isinstance(params, dict):
        return name
    path = params.get("file_path") or params.get("notebook_path")
    if isinstance(path, str) and path:
        return "{} {}".format(name, os.path.basename(path))
    if name == "Bash":
        command = params.get("command")
        if isinstance(command, str) and command.strip():
            program = _main_program(command)
            if program:
                return "Bash {}".format(program)
    if name in ("Agent", "Task"):
        sub = params.get("subagent_type")
        if isinstance(sub, str) and sub:
            return "{} {}".format(name, sub)
    return name


_BORING = {"cd", "export", "set", "source", ".", "env", "sudo", "time", "nohup", "exec"}


def _main_program(command: str) -> str:
    """First meaningful program of a shell command, without arguments (they may hold secrets)."""
    for segment in re.split(r"&&|\|\||;|\|", command):
        for word in segment.strip().split():
            if "=" in word.split("/")[0] or word in _BORING:
                if word in ("cd", "source", "."):
                    break  # skip the whole segment (its argument is a path)
                continue
            if word.startswith("-"):
                continue
            name = os.path.basename(word.strip("'\"()"))
            if re.fullmatch(r"[A-Za-z0-9_.+-]{1,32}", name):
                return name
            break
    return ""


@dataclass
class Ask:
    ts: float
    text: str
    reply: str = ""          # agent's latest message for this ask
    reply_ts: Optional[float] = None

    @property
    def key(self) -> str:
        return hashlib.sha1("{:.3f}|{}".format(self.ts, self.text).encode("utf-8")).hexdigest()[:16]


@dataclass
class SessionData:
    asks: List[Ask] = field(default_factory=list)
    title: str = ""
    permission_mode: str = ""
    model: str = ""
    effort: str = ""
    context_tokens: Optional[int] = None
    last_tool: str = ""
    last_tool_ts: Optional[float] = None
    last_activity_ts: Optional[float] = None
    files: "OrderedDict[str, float]" = field(default_factory=OrderedDict)
    todos: Optional[Tuple[int, int, str]] = None
    last_reply: str = ""                  # latest assistant text after the current ask
    last_reply_ts: Optional[float] = None


class Transcript:
    def __init__(self, path: Path):
        self.path = path
        self.offset = 0
        self.size = -1
        self.data = SessionData()
        self._loaded = False

    def refresh(self) -> bool:
        """Read new bytes. Returns True when something changed."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return False
        if size == self.size and self._loaded:
            return False
        if size < self.offset:  # rewritten or truncated
            self.offset = 0
            self.data = SessionData()
            self._loaded = False
        if not self._loaded:
            start = max(0, size - INITIAL_TAIL)
            self._read_range(start, size, skip_partial=start > 0)
            self._backfill(start)
            self._loaded = True
        else:
            end = min(size, self.offset + MAX_READ_PER_REFRESH)
            self._read_range(self.offset, end, skip_partial=False)
        self.size = size
        return True

    # -- reading -----------------------------------------------------------
    def _read_range(self, start: int, end: int, skip_partial: bool) -> None:
        if end <= start:
            return
        with open(self.path, "rb") as fh:
            fh.seek(start)
            blob = fh.read(end - start)
        if skip_partial:
            nl = blob.find(b"\n")
            if nl < 0:
                self.offset = end
                return
            blob = blob[nl + 1:]
        last_nl = blob.rfind(b"\n")
        if last_nl < 0:
            # No complete line yet; wait for more bytes.
            self.offset = start
            return
        complete = blob[: last_nl + 1]
        self.offset = end - (len(blob) - len(complete))
        for line in complete.splitlines():
            self._ingest_line(line)

    def _backfill(self, start: int) -> None:
        """Walk backwards to find older asks when the tail did not hold enough."""
        read = 0
        older: List[Ask] = []
        cursor = start
        while cursor > 0 and len(older) + len(self.data.asks) < WANTED_ASKS and read < BACKFILL_LIMIT:
            chunk_start = max(0, cursor - BACKFILL_CHUNK)
            with open(self.path, "rb") as fh:
                fh.seek(chunk_start)
                blob = fh.read(cursor - chunk_start)
            read += len(blob)
            if chunk_start > 0:
                nl = blob.find(b"\n")
                blob = blob[nl + 1:] if nl >= 0 else b""
            found: List[Ask] = []
            files: List[Tuple[str, float]] = []
            for line in blob.splitlines():
                obj = _loads(line)
                if obj is None:
                    continue
                text = prompt_from_record(obj)
                if text:
                    found.append(Ask(parse_ts(obj.get("timestamp")) or 0.0, text))
                elif obj.get("type") == "assistant" and not obj.get("isSidechain"):
                    ts = parse_ts(obj.get("timestamp")) or 0.0
                    for name, params in _tool_uses(obj):
                        if name in FILE_TOOLS:
                            path = params.get("file_path") or params.get("notebook_path")
                            if isinstance(path, str):
                                files.append((os.path.basename(path), ts))
            older = found + older
            for name, ts in files:
                if name not in self.data.files:
                    self.data.files[name] = ts
                    self.data.files.move_to_end(name, last=False)
            cursor = chunk_start
        if older:
            self.data.asks = (older + self.data.asks)[-KEEP_ASKS:]

    # -- parsing -----------------------------------------------------------
    def _ingest_line(self, line: bytes) -> None:
        obj = _loads(line)
        if obj is None:
            return
        d = self.data
        kind = obj.get("type")
        ts = parse_ts(obj.get("timestamp"))
        if kind == "user":
            text = prompt_from_record(obj)
            if text:
                ask = Ask(ts or 0.0, text)
                d.asks.append(ask)
                del d.asks[:-KEEP_ASKS]
                d.last_tool = ""
                d.last_tool_ts = None
                d.last_reply = ""
                d.last_reply_ts = None
                d.last_activity_ts = ts or d.last_activity_ts
        elif kind == "assistant":
            if obj.get("isSidechain"):
                return
            message = obj.get("message") or {}
            model = message.get("model")
            if isinstance(model, str) and model and not model.startswith("<"):
                d.model = model
            effort = obj.get("effort")
            if isinstance(effort, str):
                d.effort = effort
            usage = message.get("usage") or {}
            if isinstance(usage, dict) and usage:
                total = 0
                for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                    value = usage.get(key)
                    if isinstance(value, int):
                        total += value
                if total:
                    d.context_tokens = total
            if ts:
                d.last_activity_ts = ts
            text = _assistant_text(obj)
            if text:
                d.last_reply = text[-4000:]
                d.last_reply_ts = ts
                if d.asks:
                    d.asks[-1].reply = d.last_reply
                    d.asks[-1].reply_ts = ts
            for name, params in _tool_uses(obj):
                d.last_tool = tool_label(name, params)
                d.last_tool_ts = ts
                if name in FILE_TOOLS:
                    path = params.get("file_path") or params.get("notebook_path")
                    if isinstance(path, str) and path:
                        base = os.path.basename(path)
                        d.files[base] = ts or 0.0
                        d.files.move_to_end(base)
                if name == "TodoWrite":
                    todos = params.get("todos")
                    if isinstance(todos, list):
                        done = sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed")
                        now = next((str(t.get("activeForm") or t.get("content") or "") for t in todos
                                    if isinstance(t, dict) and t.get("status") == "in_progress"), "")
                        d.todos = (done, len(todos), now)
        elif kind == "permission-mode":
            mode = obj.get("permissionMode")
            if isinstance(mode, str):
                d.permission_mode = mode
        elif kind == "ai-title":
            title = obj.get("aiTitle")
            if isinstance(title, str):
                d.title = title
        elif kind == "system" and obj.get("subtype") == "compact_boundary":
            d.context_tokens = None


def _loads(line: bytes) -> Optional[dict]:
    line = line.strip()
    if not line or line[:1] != b"{":
        return None
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _assistant_text(obj: dict) -> str:
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return ""
    parts = [b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p.strip()).strip()


def _tool_uses(obj: dict):
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            params = block.get("input")
            yield str(block.get("name") or "tool"), params if isinstance(params, dict) else {}


# -- locating transcripts ------------------------------------------------------
_glob_cache: Dict[str, Optional[Path]] = {}


def find_transcript(session_id: Optional[str], cwd: Optional[str]) -> Tuple[Optional[Path], bool]:
    """Return (path, inferred). inferred=True when herdr gave no session id."""
    base = claude_dir() / "projects"
    if session_id and re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        if cwd:
            direct = base / encode_project_dir(cwd) / "{}.jsonl".format(session_id)
            if direct.exists():
                return direct, False
        cached = _glob_cache.get(session_id)
        if cached and cached.exists():
            return cached, False
        for found in base.glob("*/{}.jsonl".format(session_id)):
            _glob_cache[session_id] = found
            return found, False
        return None, False
    if not cwd:
        return None, True
    folder = base / encode_project_dir(cwd)
    try:
        newest = max(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    except (ValueError, OSError):
        return None, True
    return newest, True


def read_tasks(session_id: Optional[str]) -> Optional[Tuple[int, int, str]]:
    """Claude Code task list (~/.claude/tasks/<session>/*.json): (completed, total, current)."""
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        return None
    folder = claude_dir() / "tasks" / session_id
    if not folder.is_dir():
        return None
    done = total = 0
    current = ""
    for path in folder.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as fh:
                task = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(task, dict) or task.get("status") == "deleted":
            continue
        total += 1
        if task.get("status") == "completed":
            done += 1
        elif task.get("status") == "in_progress" and not current:
            current = str(task.get("activeForm") or task.get("subject") or "")
    return (done, total, current) if total else None


# -- model naming --------------------------------------------------------------
def model_name(model_id: str) -> Tuple[str, str]:
    """'claude-opus-5-5[1m]' -> ('Opus', '5.5'). Unknown ids are returned as-is."""
    if not model_id:
        return "", ""
    mid = model_id.split("[", 1)[0]
    m = re.match(r"^(?:claude-)?([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?$", mid)
    if m:
        family = m.group(1).capitalize()
        version = m.group(2) + ("." + m.group(3) if m.group(3) else "")
        return family, version
    m = re.match(r"^claude-(\d+)(?:-(\d))?-([a-z]+)", mid)  # legacy: claude-3-5-sonnet
    if m:
        return m.group(3).capitalize(), m.group(1) + ("." + m.group(2) if m.group(2) else "")
    return mid, ""
