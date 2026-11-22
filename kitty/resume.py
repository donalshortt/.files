#!/usr/bin/python3
"""Save and reopen Kitty windows attached to persistent SSH sessions on lap."""

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


def kitty_snapshots():
    sources = terminal_sources(include_all=True)
    return [kitty_request(source, "resume_snapshot") for source in sources.values()]


def save(path):
    snapshots = kitty_snapshots()
    unmanaged = sum(snapshot["unmanaged"] for snapshot in snapshots)
    if unmanaged:
        raise RuntimeError(
            f"{unmanaged} existing SSH login(s) to lap could not be saved. "
            "Finish or move that work into a managed session before running sd. "
            "New interactive `ssh lap` connections from Kitty use Screen automatically."
        )

    locations = desktop_locations()
    windows = []
    for snapshot in snapshots:
        for window in snapshot["windows"]:
            location = locations.get(window["x11_id"])
            if location is None:
                raise RuntimeError("A Kitty window changed during the snapshot. Run sd again.")
            windows.append({
                "desktop": location["desktop"],
                "screens": window["screens"],
                "session": window["session"],
            })

    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(windows, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Saved {len(windows)} Kitty window(s) for resume.", flush=True)


def check_lap():
    try:
        subprocess.run(
            ["ssh", "-nT", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             "lap", "command -v screen >/dev/null"],
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


def restore(path):
    if not path.exists():
        raise RuntimeError("No saved SSH layout. Run `resume save` or `sd` first.")
    windows = json.loads(path.read_text())
    if not windows:
        print("The saved layout has no SSH windows.")
        return

    locations = desktop_locations(include_details=True)
    live_tags = {location["instance"].rpartition("-")[0] for location in locations.values()}
    live_screens = {
        screen for snapshot in kitty_snapshots() for window in snapshot["windows"]
        for screen in window["screens"]
    }
    pending = {}
    for window in windows:
        screens = set(window["screens"])
        tag = "lap-" + window["screens"][0]
        if screens <= live_screens:
            continue
        if tag in live_tags or screens & live_screens:
            raise RuntimeError(
                f"A saved window on desktop {window['desktop']} is open with only part of its session. "
                "Close that local window before retrying."
            )
        instance = f"{tag}-{desktop_id(window['desktop'])}"
        pending[instance] = window

    if not pending:
        print("The saved SSH windows are already open.")
        return
    check_lap()

    session = "\nnew_os_window\n".join(
        f"os_window_name {instance}\n{quiet_saved_session(window['session'])}\n"
        for instance, window in pending.items()
    )
    subprocess.run(
        ["kitty", "--detach", "--session", "-"], input=session, text=True,
        check=True, timeout=10,
    )

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
    args = parser.parse_args()
    directory = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "kitty-resume"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            action = save if args.action == "save" else restore
            action(directory / "snapshot.json")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"resume: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
