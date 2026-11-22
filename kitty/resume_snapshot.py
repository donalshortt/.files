"""Capture resumable SSH panes from inside a running Kitty instance."""

import json
from pathlib import Path
from runpy import run_path
import shlex

from kitty.child import cached_process_data
from kitty.constants import unserialize_launch_flag
from kitty.launch import parse_launch_args
from kitty.session import default_save_as_session_opts
from kitty.utils import platform_window_id


# The Kitty handler's sibling scripts are loaded by path.
_ssh = run_path(str(Path(__file__).with_name("resume_ssh.py")))
ssh_args = _ssh["ssh_args"]
screen_session = _ssh["screen_session"]
is_interactive_lap_ssh = _ssh["is_interactive_lap_ssh"]


def safe_session(lines, sessions_by_id):
    session = []
    restored_ids = set()
    screens = {}
    for line in lines:
        if len(line.splitlines()) > 1:
            raise ValueError("A Kitty tab title or path contains a line break")
        if line.startswith(("os_window_class ", "os_window_name ")):
            continue  # The desktop launcher assigns an identity for placement.
        if line.startswith("launch "):
            _, metadata, *arguments = shlex.split(line)
            if not metadata.startswith(unserialize_launch_flag):
                raise ValueError("Kitty did not provide a pane identity for restore")
            pane_id = json.loads(metadata[len(unserialize_launch_flag):])["id"]
            if pane_id not in sessions_by_id or pane_id in restored_ids:
                raise ValueError("Kitty returned an unexpected pane in its snapshot")
            restored_ids.add(pane_id)
            name, screen = sessions_by_id[pane_id]
            screens[name] = None

            # Retain the ID Kitty uses to resolve its split tree. Rebuild the
            # command rather than replaying the pane's original program or env.
            options = parse_launch_args(arguments).opts
            launch = ["launch", unserialize_launch_flag + json.dumps({"id": pane_id})]
            if options.cwd:
                launch.append(f"--cwd={options.cwd}")
            if options.type in ("overlay", "overlay-main"):
                launch.append(f"--type={options.type}")
            line = shlex.join(launch + ssh_args(name, screen))
        session.append(line)

    if restored_ids != sessions_by_id.keys():
        raise ValueError("Kitty could not save every managed SSH pane")
    return "\n".join(session) + "\n", list(screens)


def snapshot(boss):
    by_os_window = {}
    unmanaged = set()
    with cached_process_data():
        for pane in boss.all_windows:
            if pane.destroyed:
                continue
            matches = set()
            for process in pane.child.foreground_processes:
                argv = process.get("cmdline") or ()
                screen = screen_session(argv)
                if screen is not None:
                    matches.add(screen)
                elif is_interactive_lap_ssh(argv):
                    unmanaged.add(process["pid"])
            if len(matches) > 1:
                raise ValueError("One Kitty pane contains multiple managed SSH sessions")
            if matches:
                by_os_window.setdefault(pane.os_window_id, {})[pane] = matches.pop()

    windows = []
    options = default_save_as_session_opts()
    for manager in boss.all_tab_managers:
        panes = by_os_window.pop(manager.os_window_id, None)
        if not panes:
            continue
        x11_id = platform_window_id(manager.os_window_id)
        if not x11_id:
            raise ValueError("Could not find the bspwm window for a managed SSH pane")
        lines = manager.serialize_state_as_session("", frozenset(panes), options, is_first=True)
        session, screens = safe_session(lines, {pane.id: screen for pane, screen in panes.items()})
        windows.append({"x11_id": x11_id, "session": session, "screens": screens})
    if by_os_window:
        raise ValueError("A Kitty window disappeared while taking the SSH snapshot")
    return {"windows": windows, "unmanaged": len(unmanaged)}
