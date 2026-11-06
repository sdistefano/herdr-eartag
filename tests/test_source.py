"""Input adapters (herdr TUI pane vs herdr-core terminal) and the `json` payload."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_eartag import herdr, pad, payload, source  # noqa: E402
from herdr_eartag.config import Config  # noqa: E402
from herdr_eartag.i18n import Tr  # noqa: E402
from herdr_eartag.panel import PanelModel  # noqa: E402
from herdr_eartag.render import Bar, View  # noqa: E402

# What `hc get t18 --json` prints for a Claude agent (trimmed to the fields we read).
HC_T18 = {
    "address": "t18",
    "cwd": "/home/agent",
    "foreground": {
        "argv": ["claude"],
        "cwd": "/home/agent/proj/gaucho",
        "name": "claude",
        "pid": 3297601,
    },
    "labels": {"herdr.space": "sp9c", "herdr.tab": "tb86", "where": "gaucho / 1"},
    "state": "live",
    "status": {"app": "claude-code", "state": "working"},
}
SESSION = {
    "pid": 3297601,
    "sessionId": "f3692ac2-5c10-48d3-91f2-97727dc6b5df",
    "cwd": "/home/agent/proj/gaucho",
}


class FakeRunner:
    """Answers argv prefixes with (code, stdout) and records every call."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, argv, env=None):
        self.calls.append((argv, env))
        for prefix, answer in self.answers.items():
            if tuple(argv[: len(prefix)]) == prefix:
                return answer
        return 1, ""


def _sessions_dir(tmp, sessions=(SESSION,)):
    folder = Path(tmp) / "sessions"
    folder.mkdir()
    for sess in sessions:
        (folder / "{}.json".format(sess["pid"])).write_text(json.dumps(sess))
    return folder


class CoreSourceTests(unittest.TestCase):
    def test_pane_from_terminal_and_session_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRunner({("hc", "get", "t18"): (0, json.dumps(HC_T18))})
            src = source.CoreSource(run=run, sessions_dir=_sessions_dir(tmp))
            pane = src.pane("t18")
        self.assertEqual(pane["agent"], "claude")
        self.assertEqual(pane["agent_status"], "working")
        self.assertEqual(pane["agent_session"], {"value": SESSION["sessionId"]})
        self.assertEqual(pane["foreground_cwd"], "/home/agent/proj/gaucho")
        self.assertEqual(pane["pane_id"], "t18")
        self.assertEqual((pane["tab_id"], pane["workspace_id"]), ("tb86", "sp9c"))

    def test_missing_terminal_is_none(self):
        run = FakeRunner({("hc", "get"): (1, "")})
        self.assertIsNone(
            source.CoreSource(run=run, sessions_dir=Path("/nonexistent")).pane("t99")
        )

    def test_shell_without_agent_has_no_session(self):
        term = dict(
            HC_T18, foreground={"name": "zsh", "pid": 1, "cwd": "/tmp"}, status=None
        )
        run = FakeRunner({("hc", "get"): (0, json.dumps(term))})
        pane = source.CoreSource(run=run, sessions_dir=Path("/nonexistent")).pane("t18")
        self.assertEqual(pane["agent"], "")
        self.assertIsNone(pane["agent_session"])

    def test_codex_agent_is_named_by_its_report(self):
        term = dict(
            HC_T18,
            status={"app": "codex", "state": "idle"},
            foreground={"name": "node", "pid": 2},
        )
        run = FakeRunner({("hc", "get"): (0, json.dumps(term))})
        pane = source.CoreSource(run=run, sessions_dir=Path("/nonexistent")).pane("t18")
        self.assertEqual((pane["agent"], pane["agent_status"]), ("codex", "idle"))

    def test_unreachable_core_raises_herdr_error(self):
        def broken(argv, env=None):
            raise OSError("no hc")

        with self.assertRaises(herdr.HerdrError):
            source.CoreSource(run=broken, sessions_dir=Path("/nonexistent")).pane("t18")

    def test_agents_lists_other_agent_terminals(self):
        shell = {
            "address": "t3",
            "cwd": "/",
            "foreground": {"name": "zsh"},
            "status": None,
        }
        run = FakeRunner({("hc", "ls"): (0, json.dumps([HC_T18, shell]))})
        agents = source.CoreSource(run=run, sessions_dir=Path("/nonexistent")).agents()
        self.assertEqual([a["pane_id"] for a in agents], ["t18"])

    def test_pad_path_asks_scratch_as_that_terminal(self):
        run = FakeRunner(
            {("scratch", "--path"): (0, "/var/scratchpad/hc-gaucho:1.md\n")}
        )
        found = source.CoreSource(run=run).pad_path({"pane_id": "t2"})
        self.assertEqual(found, Path("/var/scratchpad/hc-gaucho:1.md"))
        env = run.calls[0][1]
        self.assertEqual((env["HC_TERMINAL_ID"], env["SCRATCH_GUARD"]), ("t2", "off"))

    def test_no_pad_when_scratch_exits_3(self):
        run = FakeRunner({("scratch", "--path"): (3, "")})
        self.assertIsNone(source.CoreSource(run=run).pad_path({"pane_id": "t2"}))

    def test_start_pad_binds_it_to_the_agent_session(self):
        run = FakeRunner(
            {
                ("scratch", "--set-session"): (0, ""),
                ("scratch", "--path"): (0, "/var/scratchpad/hc-gaucho:2.md\n"),
            }
        )
        found = source.CoreSource(run=run).start_pad({"pane_id": "t18"}, "f369")
        self.assertEqual(found, Path("/var/scratchpad/hc-gaucho:2.md"))
        argv, env = run.calls[0]
        self.assertEqual(argv, ["scratch", "--set-session", "f369"])
        self.assertEqual(env["HC_TERMINAL_ID"], "t18")

    def test_start_pad_without_a_session_seeds_it(self):
        run = FakeRunner(
            {("scratch", "--seed"): (0, ""), ("scratch", "--path"): (0, "/p.md\n")}
        )
        source.CoreSource(run=run).start_pad({"pane_id": "t18"}, None)
        self.assertEqual(run.calls[0][0], ["scratch", "--seed"])

    def test_start_pad_reports_none_when_no_pad_can_resolve(self):
        run = FakeRunner({("scratch",): (3, "")})
        self.assertIsNone(
            source.CoreSource(run=run).start_pad({"pane_id": "t18"}, "f369")
        )

    def test_tool_path_adds_box_bin_folders(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}):
            path = source.tool_path()
        parts = path.split(os.pathsep)
        self.assertIn(str(Path.home() / ".local" / "bin"), parts)
        self.assertIn(str(Path.home() / ".bin"), parts)
        self.assertEqual(parts[-1], "/usr/bin")


class FakeSource:
    """A source with a fixed pane: the panel must not reach herdr at all."""

    def __init__(self, pane):
        self._pane = pane
        self.pad_asks = 0

    def pane(self, target):
        return self._pane

    def agents(self):
        return []

    def pad_path(self, pane):
        self.pad_asks += 1
        return None

    def scratch_available(self):
        return False


class PanelSourceTests(unittest.TestCase):
    def test_panel_polls_its_source_not_herdr(self):
        pane = {
            "pane_id": "t18",
            "agent": "codex",
            "agent_status": "idle",
            "cwd": "/nonexistent",
        }
        src = FakeSource(pane)
        model = PanelModel("t18", Config(), Tr("en"), source=src)
        with mock.patch.object(
            herdr, "pane_get", side_effect=AssertionError("herdr called")
        ):
            model.poll()
        self.assertEqual(model.status, "idle")
        self.assertEqual(model.agent, "codex")

    def test_pad_watcher_uses_the_given_resolver(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hc-x:1.md"
            path.write_text("## `s needed from Silvio\n- [?] which key?\n")
            watcher = pad.PadWatcher(resolver=lambda pane: path)
            watcher.available = True
            self.assertTrue(watcher.refresh({"pane_id": "t2"}))
        self.assertEqual([s.letter for s in watcher.pad.sections], ["s"])


PAD_TEXT = """## marks
```
`s  needed from Silvio
`t  todo
`a -> `t   read this now
```

## `s needed from Silvio
- [?] which key?

## `t todo
- [x] adapter
- [ ] mod
"""


def _view():
    v = View(width=40, height=36)
    v.project, v.status, v.mode_tag = "gaucho", "done", "bypass"
    v.main_kind, v.ask, v.reply_verdict = "last", "Add a json subcommand", "DONE"
    v.notif = ("Your turn: review", "done")
    v.before = [("10:02", "Pad tab", "DONE")]
    v.files, v.diff = ["cli.py", "source.py"], (40, 3)
    v.bars = [Bar("ctx", "CTX", 31.0, "ctx", "62k / 200k"), Bar("h5", "5H", 12.5)]
    v.tasks, v.task_now = (2, 5), "Writing tests"
    v.model, v.effort, v.effort_level = "Opus", "high", (4, 5)
    v.menu, v.hover_mark = [("x", "y", "z", "w")], "s"  # TUI-only: must not leak
    return v


class PayloadTests(unittest.TestCase):
    def test_view_as_data(self):
        data = payload.view_data(_view())
        self.assertEqual(data["project"], "gaucho")
        self.assertEqual(data["notif"], {"text": "Your turn: review", "role": "done"})
        self.assertEqual(
            data["before"], [{"time": "10:02", "title": "Pad tab", "verdict": "DONE"}]
        )
        self.assertEqual(data["diff"], {"added": 40, "removed": 3})
        self.assertEqual(data["tasks"], {"done": 2, "total": 5, "now": "Writing tests"})
        self.assertEqual(data["effort_level"], {"filled": 4, "total": 5})
        self.assertEqual(data["bars"][0]["detail"], "62k / 200k")
        for tui_only in (
            "menu",
            "menu_index",
            "hover_mark",
            "width",
            "height",
            "ascii",
            "selected_bar",
            "marks",
        ):
            self.assertNotIn(tui_only, data)

    def test_pad_as_data(self):
        parsed = pad.parse(PAD_TEXT, Path("/var/scratchpad/hc-gaucho:1.md"))
        data = payload.pad_data(parsed)
        self.assertEqual(data["path"], "/var/scratchpad/hc-gaucho:1.md")
        self.assertEqual(data["todo"], {"done": 1, "total": 3})  # [?] counts too
        self.assertEqual([m["letter"] for m in data["marks"]], ["a", "s", "t"])
        marks = {m["letter"]: m for m in data["marks"]}
        self.assertEqual(marks["a"]["line"], parsed.line_of("t"))
        self.assertEqual(marks["s"]["role"], "working b")
        self.assertEqual(marks["t"]["count"], "1/3")
        self.assertEqual(
            data["sections"][0],
            {"letter": "s", "title": "needed from Silvio", "line": 8, "filled": True},
        )
        self.assertEqual(data["glossary"]["t"], "todo")

    def test_pad_carries_an_app_nvim(self):
        parsed = pad.parse(PAD_TEXT, Path("/var/scratchpad/hc-gaucho:1.md"))
        nvim = payload.pad_data(parsed)["nvim"]
        self.assertEqual(nvim["argv"][0], "nvim")
        self.assertEqual(nvim["argv"][-1], "/var/scratchpad/hc-gaucho:1.md")
        self.assertNotIn(
            str(pad.TABBAR_LUA), nvim["argv"]
        )  # the app draws its own tab bar
        listen = nvim["argv"].index("--listen")
        self.assertEqual(nvim["argv"][listen + 1], nvim["socket"])
        other = payload.pad_data(
            pad.parse(PAD_TEXT, Path("/var/scratchpad/other:2.md"))
        )
        self.assertNotEqual(nvim["socket"], other["nvim"]["socket"])  # one nvim per pad

    def test_no_pad_is_null(self):
        self.assertIsNone(payload.pad_data(None))

    def test_document_is_json(self):
        doc = payload.document("t2", "f369", _view(), None, error="")
        text = json.dumps(doc)
        back = json.loads(text)
        self.assertEqual(back["terminal"], "t2")
        self.assertEqual(back["session_id"], "f369")
        self.assertEqual(back["view"]["reply_verdict"], "DONE")
        self.assertIsNone(back["pad"])
        self.assertEqual(back["schema"], payload.SCHEMA)


class CachedSummarizerTests(unittest.TestCase):
    def _summarizer(self, tmp):
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": tmp}):
            with mock.patch(
                "herdr_eartag.summarize.resolve_backend",
                return_value=("claude", "/bin/true"),
            ):
                return payload.CachedSummarizer("claude")

    def test_miss_claims_once_and_never_starts_a_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = self._summarizer(tmp), self._summarizer(tmp)
            with mock.patch(
                "threading.Thread", side_effect=AssertionError("thread started")
            ):
                self.assertIsNone(first.get("title", "Add a json subcommand", 30))
                self.assertIsNone(second.get("title", "Add a json subcommand", 30))
            self.assertEqual(len(first.todo), 1)
            self.assertEqual(second.todo, [])  # another process already claimed it
            self.assertTrue(second.pending("title", "Add a json subcommand", 30))

    def test_stale_claim_is_taken_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._summarizer(tmp)
            first.get("title", "x y z", 30)
            claim = first.claim_path(first.todo[0][0])
            old = time.time() - payload.CLAIM_TTL - 5
            os.utime(claim, (old, old))
            second = self._summarizer(tmp)
            second.get("title", "x y z", 30)
            self.assertEqual(len(second.todo), 1)

    def test_cached_answer_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            summ = self._summarizer(tmp)
            summ._cache[summ._key("title", "x y z", 30)] = "Json subcommand"
            self.assertEqual(summ.get("title", "x y z", 30), "Json subcommand")
            self.assertEqual(summ.todo, [])


if __name__ == "__main__":
    unittest.main()
