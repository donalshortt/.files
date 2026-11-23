#!/usr/bin/python3
"""Save and restore Kitty terminals and persistent SSH sessions."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from desktop import desktop_locations, kitty_request, terminal_sources
from resume_ssh import quiet_saved_session


def kitty_snapshots(*, capture=True):
    request = {"capture": capture, "caller_pid": os.getpid()}
    return [kitty_request(source, "resume_snapshot", request)
            for source in terminal_sources(include_all=True).values()]


def check_coverage(snapshots, locations):
    expected = {x11_id for x11_id, location in locations.items()
                if location["class_name"].casefold() == "kitty"}
    captured = {window["x11_id"] for snapshot in snapshots for window in snapshot["windows"]}
    if expected - captured:
        raise RuntimeError(f"Could not read {len(expected - captured)} Kitty window(s). Try again once they are ready.")
    if captured - locations.keys():
        raise RuntimeError("A Kitty window changed during the snapshot. Try again.")


def save(path, *, force=False):
    snapshots = kitty_snapshots()
    locations = desktop_locations(include_details=True)
    check_coverage(snapshots, locations)
    windows = []
    for snapshot in snapshots:
        for window in snapshot["windows"]:
            windows.append({
                **window,
                "instance": snapshot["instance"],
                "desktop": locations[window["x11_id"]]["desktop"],
            })

    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump({"saved_at": time.time(), "windows": windows}, output)
            output.flush()
            os.fsync(output.fileno())
            os.replace(temporary, path)
            descriptor = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
    panes = sum(len(window["scrollback"]) for window in windows)
    print(f"Saved {panes} Kitty pane(s) in {len(windows)} window(s), including terminal output.", flush=True)

    work = {}
    for window in windows:
        for programs in window["unrestorable"].values():
            work.setdefault(window["desktop"], []).extend(programs)
    if work:
        details = "\n".join(f"  Desktop {desktop} ({', '.join(sorted(set(programs)))})" for desktop, programs in work.items())
        message = f"Shutdown would disconnect unmanaged SSH logins.\n{details}"
        if not force:
            raise RuntimeError(
                f"{message}\nClose those logins or move them into Screen, or use `sd --force` to shut down with this snapshot."
            )
        print(f"resume: {message}", file=sys.stderr, flush=True)


def check_lap():
    try:
        subprocess.run(
            ["ssh", "-nT", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "lap", 'command -v screen >/dev/null || test -x "$HOME/.local/bin/screen5"'],
            check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Could not reach GNU Screen on lap. Try resume again once lap is ready.") from error


def desktop_id(name):
    query = subprocess.run(
        ["bspc", "query", "-D", "-d", f"%{name}"],
        capture_output=True, text=True, timeout=3,
    )
    identifier = query.stdout.strip().lower()
    if query.returncode or not re.fullmatch(r"0x[0-9a-f]+", identifier):
        raise RuntimeError(f"Saved bspwm desktop {name!r} is unavailable.")
    return identifier


def session_text(windows):
    return "\nnew_os_window\n".join(
        f"os_window_name {instance}\n{quiet_saved_session(window['session'])}\n"
        for instance, window in windows.items()
    )


def launch_restored_groups(pending, directory, saved_at):
    # Kitty uses one set of pane IDs per instance. Keep the original groups so
    # each pane gets its own scrollback even if pane IDs repeat across groups.
    groups = {}
    for tag, window in pending.items():
        groups.setdefault(window["instance"], {})[tag] = window

    snapshots = directory / "snapshots"
    snapshots.mkdir()
    for index, group in enumerate(groups.values()):
        native = snapshots / str(index)
        history = native / "scrollback"
        history.mkdir(parents=True)
        (native / "session.kitty-session").write_text(session_text(group))
        (native / "process.json").write_text(json.dumps({
            "argv": [], "cwd": str(Path.home()), "environ": {}, "saved_at": saved_at,
        }))
        for window in group.values():
            for pane_id, contents in window["scrollback"].items():
                (history / str(int(pane_id))).write_text(contents)
        subprocess.run(
            ["kitty", "--detach", "--session", "none"],
            env=dict(os.environ, KITTY_RESTORE_LOGOUT_SNAPSHOT=str(native), KITTY_RESUME_LITERAL_DOLLAR="$"),
            check=True, timeout=10,
        )


def restore(path):
    if not path.exists():
        raise RuntimeError("No saved Kitty layout. Run `resume save` or `sd` first.")
    data = json.loads(path.read_text())
    legacy = isinstance(data, list)
    windows = data if legacy else data["windows"]
    if not windows:
        print("The saved layout has no Kitty windows.")
        return

    locations = desktop_locations(include_details=True)
    snapshots = kitty_snapshots(capture=False)
    check_coverage(snapshots, locations)
    live = {window["id"]: window for snapshot in snapshots for window in snapshot["windows"]}
    live_tags = {location["instance"].rpartition("-")[0]: x11_id for x11_id, location in locations.items()}
    live_by_x11 = {window["x11_id"]: window for window in live.values()}
    live_screens = {screen for window in live.values() for screen in window["screens"]}
    pending = {}
    for window in windows:
        screens = set(window["screens"])
        if legacy:
            tag = "lap-" + window["screens"][0]
            if screens <= live_screens:
                continue
        else:
            tag = "kitty-resume-" + window["id"]
            if window["id"] in live:
                continue
            if tag in live_tags:
                restored = live_by_x11.get(live_tags[tag])
                if restored and screens <= set(restored["screens"]) and (
                    restored["pane_count"] >= len(window["scrollback"])
                ):
                    continue
                raise RuntimeError(
                    f"The restored Kitty window on desktop {window['desktop']} is missing some panes or Screen sessions. "
                    "Close that window before retrying."
                )
        if tag in live_tags or screens & live_screens:
            raise RuntimeError(
                f"Some saved Screen sessions on desktop {window['desktop']} are already attached to a Kitty window. "
                "Close the duplicate connection before retrying."
            )
        instance = f"{tag}-{desktop_id(window['desktop'])}"
        pending[instance] = window

    if not pending:
        print("The saved Kitty windows are already open.")
        return
    if any(window["screens"] for window in pending.values()):
        check_lap()

    with tempfile.TemporaryDirectory(prefix="restore-", dir=path.parent) as directory:
        if legacy:
            subprocess.run(
                ["kitty", "--detach", "--session", "-"], input=session_text(pending), text=True,
                check=True, timeout=10,
            )
        else:
            launch_restored_groups(pending, Path(directory), data["saved_at"])

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            opened = {
                location["instance"]: location["desktop"]
                for location in desktop_locations(include_details=True).values()
                if location["instance"] in pending
            }
            if opened.keys() == pending.keys():
                if any(opened[instance] != window["desktop"] for instance, window in pending.items()):
                    raise RuntimeError("A Kitty window opened on the wrong desktop. Check the bspwm external rule.")
                print(f"Opened {len(opened)} Kitty window(s).")
                return
            time.sleep(0.1)
    raise RuntimeError("Some Kitty windows did not open. Run resume again to retry them.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, prog="resume")
    parser.add_argument("action", choices=("save",), nargs="?")
    parser.add_argument("--force", action="store_true", help="allow shutdown with unmanaged SSH logins")
    args = parser.parse_args()
    if args.force and args.action != "save":
        parser.error("--force requires save")
    directory = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "kitty-resume"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if args.action == "save":
                save(directory / "snapshot.json", force=args.force)
            else:
                restore(directory / "snapshot.json")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"resume: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
