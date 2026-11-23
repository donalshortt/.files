"""Capture the layout, output, and running work of every Kitty terminal."""

from hashlib import blake2s
import json
import os
from pathlib import Path
from runpy import run_path
import shlex

from kitty.child import cached_process_data
from kitty.constants import unserialize_launch_flag
from kitty.launch import parse_launch_args
from kitty.logout_session import scrollback_for_restore
from kitty.session import default_save_as_session_opts
from kitty.utils import path_from_osc7_url, platform_window_id


# The Kitty handler's sibling scripts are loaded by path.
_ssh = run_path(str(Path(__file__).with_name("resume_ssh.py")))
ssh_args = _ssh["ssh_args"]
screen_session = _ssh["screen_session"]
interactive_ssh = _ssh["interactive_ssh"]
reconnect_login = _ssh["reconnect_login"]
SHELLS = {"bash", "dash", "fish", "ksh", "mksh", "nu", "sh", "tcsh", "zsh"}


def identity(value):
    return blake2s(value.encode(), digest_size=16).hexdigest()


def safe_session(lines, panes):
    session = []
    restored_ids = set()
    for line in lines:
        if line.startswith(("os_window_class ", "os_window_name ", "cd ")):
            continue  # Use the resume window's placement identity and an explicit cwd for each pane.
        if line.splitlines() not in ([], [line]):
            raise ValueError("A Kitty tab title or path contains a line break")
        if line.startswith("launch "):
            _, metadata, *arguments = shlex.split(line)
            if not metadata.startswith(unserialize_launch_flag):
                raise ValueError("Kitty did not provide a pane identity for restore")
            pane_id = json.loads(metadata[len(unserialize_launch_flag):])["id"]
            if pane_id not in panes or pane_id in restored_ids:
                raise ValueError("Kitty returned an unexpected pane in its snapshot")
            restored_ids.add(pane_id)
            pane = panes[pane_id]

            # Keep the ID and appearance settings Kitty needs for its layout.
            # Commands and environment variables from the original launch are excluded.
            options = parse_launch_args(arguments).opts
            launch = ["launch", unserialize_launch_flag + json.dumps({"id": pane_id})]
            if pane["cwd"]:
                # Kitty expands session options, then expands the working directory again.
                cwd = pane["cwd"].replace("$", "$${KITTY_RESUME_LITERAL_DOLLAR}")
                launch.append(f"--cwd={cwd}")
            if options.window_title:
                launch.append("--title=" + options.window_title.replace("$", "$$"))
            if options.type != "window":
                launch.append(f"--type={options.type}")
            if options.type in ("window-dock", "tab-dock", "os-window-dock"):
                launch.extend((f"--dock-edge={options.dock_edge}", f"--dock-size={options.dock_size}"))
                if options.dock_skip_focus:
                    launch.append("--dock-skip-focus")
            line = shlex.join(launch + pane["command"])
            if line.splitlines() != [line]:
                raise ValueError("A Kitty pane title or path contains a line break")
        session.append(line)

    if restored_ids != panes.keys():
        raise ValueError("Kitty could not save every terminal pane")
    return "\n".join(session) + "\n"


def process_name(process):
    argv = process.get("cmdline") or ()
    name = os.path.basename(argv[0]).lstrip("-") if argv else ""
    return "".join(char if char.isprintable() else "?" for char in name) or "unknown process"


def pane_state(pane, foreground, managed, caller_pid):
    command = ssh_args(*managed) if managed else []
    work = set()
    unrestorable = set()
    if not managed and not any(process["pid"] == caller_pid for process in foreground):
        for process in foreground:
            argv = process.get("cmdline") or ()
            login = interactive_ssh(argv)
            if login:
                host = login[0]
                reported = os.fsdecode(pane.screen.last_reported_cwd or "")
                # OSC 7 can still contain the local shell's directory.
                reported_host = reported.partition("://")[2].partition("/")[0]
                cwd = path_from_osc7_url(reported) if reported_host == host.rsplit("@", 1)[-1] else ""
                reconnect = reconnect_login(login, cwd)
                if not command and reconnect:
                    command = reconnect
                unrestorable.add(f"SSH login to {host}")
            else:
                name = process_name(process)
                if process["pid"] != pane.child.root_pid or name not in SHELLS:
                    work.add(name)
    for process in pane.child.background_processes:
        if process["pid"] != pane.child.root_pid:
            work.add(process_name(process))

    contents = scrollback_for_restore(pane.screen).decode("utf-8", "replace")
    if pane.screen.is_using_alternate_linebuf():
        visible = pane.as_text(as_ansi=True, add_wrap_markers=True)
        contents += "\r\n\x1b[m" + visible.replace("\r", "").replace("\n", "\r\n").rstrip()
    if work or unrestorable:
        contents += "\r\n\x1b[mWork open when saved: " + ", ".join(sorted(work | unrestorable))
    return {
        "command": command,
        "cwd": pane.cwd_for_serialization,
        "scrollback": contents,
        "unrestorable": sorted(unrestorable),
    }


def snapshot(boss, request):
    capture = request.get("capture", True)
    caller_pid = request.get("caller_pid")
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    start = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
    instance = identity(f"{boot}:{os.getpid()}:{start}")

    by_os_window = {}
    with cached_process_data():
        for pane in boss.all_windows:
            # Kitty UI kittens with lifecycle callbacks cannot be serialized.
            if pane.destroyed or pane.actions_on_close or pane.actions_on_focus_change or pane.actions_on_removal:
                continue
            foreground = pane.child.foreground_processes
            matches = {session for process in foreground
                       if (session := screen_session(process.get("cmdline") or ()))}
            if len(matches) > 1:
                raise ValueError("One Kitty pane contains multiple managed SSH sessions")
            managed = next(iter(matches), None)
            window = by_os_window.setdefault(pane.os_window_id, {"panes": {}, "screens": set(), "pane_count": 0})
            window["pane_count"] += 1
            if managed:
                window["screens"].add(managed[0])
            if capture:
                state = pane_state(pane, foreground, managed, caller_pid)
                window["panes"][pane.id] = state

        windows = []
        options = default_save_as_session_opts()
        for manager in boss.all_tab_managers:
            data = by_os_window.pop(manager.os_window_id, None)
            if data is None:
                continue
            x11_id = platform_window_id(manager.os_window_id)
            if not x11_id:
                raise ValueError("Could not find the bspwm window for a Kitty terminal")
            window = {
                "id": identity(f"{instance}:{manager.os_window_id}"),
                "x11_id": x11_id,
                "screens": sorted(data["screens"]),
                "pane_count": data["pane_count"],
            }
            if capture:
                panes = data["panes"]
                lines = manager.serialize_state_as_session("", None, options, is_first=True)
                window.update(
                    session=safe_session(lines, panes),
                    scrollback={pane_id: pane["scrollback"] for pane_id, pane in panes.items()},
                    unrestorable={pane_id: pane["unrestorable"] for pane_id, pane in panes.items() if pane["unrestorable"]},
                )
            windows.append(window)
    if by_os_window:
        raise ValueError("A Kitty window disappeared during the snapshot")
    return {"instance": instance, "windows": windows}
