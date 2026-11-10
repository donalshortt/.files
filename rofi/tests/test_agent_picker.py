"""Exercise selection and routing with desktop APIs mocked, never opening UI."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace as S
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("agent_picker", ROOT / "rofi/agent-picker.py")
picker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(picker)


def pane(identifier, directory, title, xid=100):
    return {"pane_id": identifier, "kitty_pid": 42, "x11_id": xid,
            "title": title, "cwd": directory,
            "processes": [{"pid": identifier + 1000, "cmdline": ["codex"]}]}


def thread(identifier, directory, title, status):
    return {"id": identifier, "cwd": directory, "name": title,
            "source": "vscode", "status": {"type": status}}


class PickerTests(unittest.TestCase):
    def entries(self):
        # Two panes in one OS window need different Kitty pane selections.
        return picker.build_entries(
            [pane(7, "/projects/a", "Implement A"), pane(9, "/projects/b", "Implement B")],
            [thread("a", "/projects/a", "Implement A", "active"),
             thread("b", "/projects/b", "Implement B", "idle")],
            {100: {"desktop": "4", "monitor": "DP-5"}},
        )

    def test_waiting_first_keeps_exact_tab_when_agents_share_a_desktop(self):
        entries = self.entries()
        self.assertEqual([(item["status"], item["pane_id"], item["desktop"]) for item in entries],
                         [("waiting", 9, "4"), ("working", 7, "4")])
        with patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "1\n", "")) as run:
            selected = picker.choose_entry(entries)
        self.assertEqual(selected["pane_id"], 7)
        command = run.call_args.args[0]
        self.assertIn("-no-sort", command)
        self.assertIn("-no-custom", command)
        self.assertEqual(command[command.index("-format") + 1], "i")

    def test_cancel_never_switches_a_terminal(self):
        with patch.object(picker, "collect_entries", return_value=self.entries()), \
                patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")) as run, \
                patch.object(picker, "activate_entry") as activate:
            self.assertEqual(picker.main([]), 0)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], "rofi")
        activate.assert_not_called()

    def test_same_directory_uses_current_title_and_never_stale_resume_argument(self):
        current = pane(7, "/projects/a", "⠹ Current task | a")
        current["processes"][0]["cmdline"] = ["codex", "resume", "old"]
        threads = [thread("old", "/projects/a", "Old task", "idle"),
                   thread("new", "/projects/a", "Current task", "active")]
        self.assertEqual(picker.match_thread(current, threads)["id"], "new")
        current["title"] = "Codex"
        self.assertIsNone(picker.match_thread(current, threads))

    def test_untrusted_titles_cannot_inject_rows_or_rofi_options(self):
        entry = self.entries()[0]
        entry["task"] = "<b>Task</b>\nFake row\0urgent\x1ftrue"
        entry["project"] = "project\rname"
        with patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")) as run:
            picker.choose_entry([entry])
        self.assertIn("-no-markup-rows", run.call_args.args[0])
        supplied = run.call_args.kwargs["input"]
        self.assertEqual(supplied.count("\n"), 1)
        self.assertNotIn("\0", supplied)
        self.assertNotIn("\x1f", supplied)

    def test_selection_routes_exact_pane_before_focusing_its_bspwm_node(self):
        selected = self.entries()[0]
        source = {"kitty_pid": 42, "pane_id": 1, "terminal": "/dev/pts/0"}
        calls = Mock()
        with patch.object(picker, "terminal_sources", return_value={42: source}), \
                patch.object(picker, "kitty_request", return_value={"ok": True}) as request, \
                patch.object(picker.subprocess, "run") as run:
            calls.attach_mock(request, "kitty")
            calls.attach_mock(run, "bspwm")
            picker.activate_entry(selected)
        target = {"pane_id": 9, "x11_id": 100, "pid": 1009}
        self.assertEqual(calls.mock_calls[0].args, (source, "focus", target))
        self.assertEqual(calls.mock_calls[1].args[0], ["bspc", "node", "0x64", "-f"])

    def test_stale_pane_never_focuses_an_os_window(self):
        with patch.object(picker, "terminal_sources", return_value={42: {}}), \
                patch.object(picker, "kitty_request", side_effect=RuntimeError("Agent closed")), \
                patch.object(picker.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                picker.activate_entry(self.entries()[0])
        run.assert_not_called()

    def test_json_inspection_never_opens_rofi_or_changes_focus(self):
        output = io.StringIO()
        with patch.object(picker, "collect_entries", return_value=self.entries()), \
                patch.object(picker.subprocess, "run") as run, contextlib.redirect_stdout(output):
            self.assertEqual(picker.main(["--json"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())), 2)
        run.assert_not_called()


class KittySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules = {
            "kittens": S(), "kittens.tui": S(),
            "kittens.tui.handler": S(result_handler=lambda **options: lambda function: function),
            "kitty": S(), "kitty.utils": S(platform_window_id=lambda identifier: identifier),
        }
        with patch.dict(sys.modules, modules):
            cls.helper = runpy.run_path(str(ROOT / "kitty/agent_picker.py"))

    def test_target_is_revalidated_before_tab_selection(self):
        window = S(id=9, destroyed=False, os_window_id=100,
                   child=S(foreground_processes=[{"pid": 1009, "cmdline": ["/usr/bin/codex"]}]))
        boss = S(window_id_map={9: window}, set_active_window=Mock(return_value=100))
        focus = self.helper["focus_pane"]
        target = {"pane_id": 9, "x11_id": 100, "pid": 1009}
        self.assertEqual(focus(boss, target), {"ok": True})
        boss.set_active_window.assert_called_once_with(window, switch_os_window_if_needed=False)
        boss.set_active_window.reset_mock()
        for invalid in ({**target, "pid": 2000}, {**target, "x11_id": 200}, {**target, "pane_id": 99}):
            with self.subTest(target=invalid), self.assertRaises(ValueError):
                focus(boss, invalid)
        boss.set_active_window.assert_not_called()


if __name__ == "__main__":
    unittest.main()
