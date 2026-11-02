"""Thin wrapper around the herdr CLI (the plugin API)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


class HerdrError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__("{}: {}".format(code, message))
        self.code = code
        self.message = message


def herdr_bin() -> str:
    return os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or "herdr"


def call(*args: str, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            [herdr_bin(), *args],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HerdrError("spawn_failed", str(exc))
    # herdr prints results on stdout and errors (JSON) on stderr.
    data: Dict[str, Any] = _last_json(proc.stdout) or _last_json(proc.stderr) or {}
    if isinstance(data, dict) and "error" in data:
        err = data["error"] or {}
        raise HerdrError(str(err.get("code", "error")), str(err.get("message", "")))
    if proc.returncode != 0:
        raise HerdrError("exit_{}".format(proc.returncode), (proc.stderr or proc.stdout).strip()[:300])
    result = data.get("result", data) if isinstance(data, dict) else {}
    return result if isinstance(result, dict) else {}


def _last_json(text: str) -> Optional[Dict[str, Any]]:
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            return value if isinstance(value, dict) else None
    return None


def _fast(method: str, params: Dict[str, Any], *cli_args: str) -> Dict[str, Any]:
    """Polling path: one socket round trip (no process spawn), CLI if the socket fails."""
    try:
        return request(method, params)
    except HerdrError as exc:
        if exc.code != "socket":
            raise
    return call(*cli_args)


def agent_list() -> List[Dict[str, Any]]:
    return list(_fast("agent.list", {}, "agent", "list").get("agents") or [])


def pane_get(pane_id: str) -> Optional[Dict[str, Any]]:
    try:
        return _fast("pane.get", {"pane_id": pane_id}, "pane", "get", pane_id).get("pane")
    except HerdrError as exc:
        if exc.code == "pane_not_found":
            return None
        raise


def pane_layout(pane_id: str) -> Dict[str, Any]:
    return call("pane", "layout", "--pane", pane_id).get("layout") or {}


def pane_resize(pane_id: str, direction: str, amount: float) -> None:
    call("pane", "resize", "--pane", pane_id, "--direction", direction, "--amount", "{:.4f}".format(amount))


def pane_close(pane_id: str) -> None:
    call("pane", "close", pane_id)


def socket_path() -> str:
    return os.environ.get("HERDR_SOCKET_PATH") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"),
        "herdr", "herdr.sock")


def request(method: str, params: Dict[str, Any], timeout: float = 2.0) -> Dict[str, Any]:
    """One raw socket API request (for methods the CLI does not expose by id)."""
    import socket
    payload = json.dumps({"id": "eartag", "method": method, "params": params}) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(socket_path())
            sock.sendall(payload.encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
    except OSError as exc:
        raise HerdrError("socket", str(exc))
    try:
        data = json.loads(buf.split(b"\n", 1)[0] or b"{}")
    except ValueError:
        raise HerdrError("socket", "invalid response")
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        raise HerdrError(str(err.get("code", "error")), str(err.get("message", "")))
    return data.get("result") or {}


def pane_focus(pane_id: str) -> None:
    request("pane.focus", {"pane_id": pane_id})


def send_text(pane_id: str, text: str) -> None:
    call("pane", "send-text", pane_id, text)


def open_panel(plugin_id: str, target_pane: str, extra_env: Dict[str, str]) -> Dict[str, Any]:
    args = [
        "plugin", "pane", "open", "--plugin", plugin_id, "--entrypoint", "panel",
        "--placement", "split", "--direction", "right", "--target-pane", target_pane,
        "--no-focus",
    ]
    for key, value in extra_env.items():
        args += ["--env", "{}={}".format(key, value)]
    return call(*args, timeout=10)


def notify(title: str, body: str = "") -> None:
    args = ["notification", "show", title, "--sound", "none"]
    if body:
        args += ["--body", body]
    try:
        call(*args)
    except HerdrError:
        pass
