"""Expose Kitty pane inventory, selection, and attention without an overlay.

Invoked by the Rofi agent picker through Kitty's no-response remote-control API.
"""

import json
import os
from pathlib import Path
import re
import tempfile

from kittens.tui.handler import result_handler
from kitty.fast_data_types import current_focused_os_window_id, request_attention
from kitty.utils import platform_window_id


def main(args):
    pass


def terminal_processes(window, commands):
    return [
        {"pid": process["pid"], "cmdline": list(process.get("cmdline") or [])}
        for process in window.child.foreground_processes
        if os.path.basename((process.get("cmdline") or [""])[0]) in commands
    ]


def inventory(boss):
    panes = []
    for window in boss.all_windows:
        if window.destroyed:
            continue
        processes = terminal_processes(window, {"codex", "ssh"})
        if not processes:
            continue
        x11_id = platform_window_id(window.os_window_id)
        if x11_id is None:
            continue
        panes.append({
            "pane_id": window.id,
            "x11_id": x11_id,
            "kitty_pid": os.getpid(),
            "title": window.title,
            "cwd": window.child.foreground_cwd or window.child.current_cwd or "",
            "processes": processes,
        })
    return {"panes": panes}


def stable_title(title):
    # Codex animates these prefixes without changing the task's identity.
    prefix = r"^(?:[\u2800-\u28ff]+\s+|[|/\\-] |(?:[●*] )?\[ [!.] \] Action Required \| )"
    return re.sub(prefix, "", title.lstrip())


def validated_window(boss, target):
    window = boss.window_id_map.get(target["pane_id"])
    if window is None or window.destroyed:
        raise ValueError("The selected agent terminal has closed")
    if platform_window_id(window.os_window_id) != target["x11_id"]:
        raise ValueError("The selected agent terminal has changed")
    command = "ssh" if "title" in target else "codex"
    if target["pid"] not in {process["pid"] for process in terminal_processes(window, {command})}:
        raise ValueError("The selected agent process is no longer in that terminal")
    if command == "ssh" and stable_title(window.title) != stable_title(target["title"]):
        raise ValueError("The selected SSH terminal has changed. Open the picker again.")
    return window


def focus_pane(boss, target):
    window = validated_window(boss, target)
    # Select the pane and its tab only. The caller focuses its bspwm node after
    # receiving this acknowledgement, and only after an explicit Rofi selection.
    if boss.set_active_window(window, switch_os_window_if_needed=False) is None:
        raise ValueError("The selected agent pane is no longer available")
    return {"ok": True}


def attention(boss, targets):
    focused = current_focused_os_window_id()
    marked = set()
    for target in targets:
        try:
            window = validated_window(boss, target)
        except ValueError:
            continue  # The pane or task changed after the inventory was read.
        if window.os_window_id != focused and window.os_window_id not in marked:
            request_attention(window.os_window_id)
            marked.add(window.os_window_id)
    return {"ok": True}


def write_response(path, response):
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=destination.parent, prefix=".agent-picker-", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(response, output)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@result_handler(no_ui=True)
def handle_result(args, result, target_window_id, boss):
    if len(args) < 3:
        return False
    try:
        if args[2] == "inventory":
            response = inventory(boss)
        elif args[2] == "focus":
            response = focus_pane(boss, json.loads(args[3]))
        elif args[2] == "attention":
            response = attention(boss, json.loads(args[3]))
        else:
            raise ValueError("Unknown agent picker action")
    except Exception as error:
        response = {"error": str(error)}
    write_response(args[1], response)
    return "error" not in response
