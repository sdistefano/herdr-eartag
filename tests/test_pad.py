import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_eartag import pad, render  # noqa: E402

PAD = """<!-- claude --resume 1234 -->
# scratch: trading:6

## marks
```
`i  intro
`s  needed from Silvio
`t  todo
`l  action log
`a -> `l:last   read this now
```

## `i intro
Eartag tabs.

## `s needed from Silvio
- [?] fork or upstream PR?

## `t todo
- [x] fork
- [/] tab bar
- [ ] tests
- [-] dropped idea

## `l action log
- 10:00 forked
- 10:30 tab bar drawn
"""


def _pad(text=PAD):
    return pad.parse(text, Path("/var/scratchpad/trading:6.md"))


class ParseTests(unittest.TestCase):
    def test_sections_carry_their_heading_line(self):
        p = _pad()
        self.assertEqual(
            [(s.letter, s.line) for s in p.sections], [("i", 13), ("s", 16), ("t", 19), ("l", 25)]
        )

    def test_a_pointing_at_last_log_line(self):
        self.assertEqual(_pad().line_of("a"), 27)

    def test_a_pointing_at_a_heading(self):
        self.assertEqual(_pad(PAD.replace("`a -> `l:last", "`a -> `s")).line_of("a"), 16)

    def test_dropped_items_leave_the_denominator(self):
        self.assertEqual(_pad().todo, (1, 4))

    def test_placeholder_is_not_a_task(self):
        self.assertEqual(_pad(PAD.replace("- [ ] tests", "- [ ] …")).todo, (1, 3))

    def test_placeholder_section_is_empty(self):
        p = _pad(PAD.replace("- [?] fork or upstream PR?", "- [ ] …"))
        self.assertFalse(next(s for s in p.sections if s.letter == "s").filled)


class ChipTests(unittest.TestCase):
    def test_order_titles_and_roles(self):
        self.assertEqual(
            pad.chips(_pad()),
            [
                ("a", "read this now · `l", "", "accent b"),
                ("i", "intro", "", "text"),
                ("s", "needed from Silvio", "1", "working b"),
                ("t", "todo", "1/4", "text"),
                ("l", "action log", "", "text"),
            ],
        )

    def test_title_falls_back_to_the_glossary(self):
        bare = PAD.replace("## `i intro", "## `i")
        self.assertEqual(pad.chips(_pad(bare))[1][:2], ("i", "intro"))

    def test_quiet_s_is_dimmed(self):
        quiet = PAD.replace("- [?] fork or upstream PR?", "")
        self.assertIn(("s", "needed from Silvio", "", "dim"), pad.chips(_pad(quiet)))

    def test_nvim_opens_at_the_line(self):
        argv = pad.nvim_argv(Path("/tmp/x.md"), 27)
        self.assertEqual(argv[0], "nvim")
        self.assertEqual(argv[-2:], ["+27", "/tmp/x.md"])
        self.assertIn(str(pad.TABBAR_LUA), argv)


class RenderTests(unittest.TestCase):
    def _frame(self, **kw):
        v = render.View(width=40, height=30, project="places", status="idle", status_label="IDLE", **kw)
        return render.render(v)

    @staticmethod
    def _text(line):
        return "".join(t for t, _ in line)

    def test_no_pad_no_tabs(self):
        frame = self._frame()
        self.assertFalse([h for h in frame.hits if h.action.startswith(("tab:", "mark:"))])

    def test_each_mark_line_carries_its_title_and_opens_its_section(self):
        frame = self._frame(pad_name="trading:6", marks=pad.chips(_pad()))
        self.assertIn("Recap", self._text(frame.lines[0]))
        marks = [h for h in frame.hits if h.action.startswith("mark:")]
        self.assertEqual([h.action for h in marks], ["mark:a", "mark:i", "mark:s", "mark:t", "mark:l"])
        rows = {h.action[5:]: self._text(frame.lines[h.y]).split() for h in marks}
        self.assertEqual(rows["s"][:4], ["`s", "needed", "from", "Silvio"])
        self.assertEqual(rows["s"][-1], "1")
        self.assertEqual(rows["t"][-1], "1/4")

    def test_hovered_mark_line_is_lit_and_only_that_one(self):
        frame = self._frame(pad_name="trading:6", marks=pad.chips(_pad()), hover_mark="s")
        ys = {h.action[5:]: h.y for h in frame.hits if h.action.startswith("mark:")}
        lit = lambda y: any("bg:tip" in style for _, style in frame.lines[y])
        self.assertTrue(lit(ys["s"]))
        self.assertFalse(any(lit(ys[k]) for k in "aitl"))

    def test_pad_tab_hit_is_on_the_tab(self):
        frame = self._frame(pad_name="trading:6", marks=pad.chips(_pad()))
        hit = next(h for h in frame.hits if h.action == "tab:pad")
        self.assertEqual(hit.y, 0)
        self.assertEqual(self._text(frame.lines[0])[hit.x0 : hit.x0 + 5].strip(), "Pad")


if __name__ == "__main__":
    unittest.main()
