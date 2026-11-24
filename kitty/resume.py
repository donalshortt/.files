#!/usr/bin/python3
"""Save and restore Kitty terminals and persistent SSH sessions."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

from desktop import desktop_locations, kitty_request, terminal_sources
from resume_ssh import prepare_saved_session


PROBE = Path(__file__).resolve().with_name("resume_remote_probe.py")


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

    screens = {name for window in windows for name in window["screens"]}
    inventory = {}
    if screens:
        try:
            inventory = lap_inventory(screens)
        except RuntimeError as error:
            print(f"resume: {error} Saved the layout without a remote work checkpoint.", file=sys.stderr)
    checkpoints = inventory.get("screens", {})
    for window in windows:
        window["checkpoints"] = {name: checkpoints[name] for name in window["screens"] if name in checkpoints}

    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump({"saved_at": time.time(), "lap_boot_id": inventory.get("boot_id"), "windows": windows}, output)
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
    conversations = sum(bool(checkpoint.get("codex")) for checkpoint in checkpoints.values())
    if conversations:
        print(f"Saved {conversations} Codex conversation checkpoint(s) from lap.", flush=True)

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


def lap_inventory(screens, *, list_only=False):
    arguments = ["python3", "-B", "-"]
    if list_only:
        arguments.append("--list")
    arguments.extend(sorted(screens))
    try:
        result = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "lap", shlex.join(arguments)],
            input=PROBE.read_text(), capture_output=True, text=True, check=True, timeout=10,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or not isinstance(data.get("screens"), dict):
            raise ValueError("Invalid Screen inventory")
        return data
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise RuntimeError("Could not read GNU Screen sessions on lap.") from error


def prepare_remote_recovery(pending, saved_boot_id):
    screens = {name for window in pending.values() for name in window["screens"]}
    if not screens:
        return
    inventory = lap_inventory(screens, list_only=True)
    missing = screens - inventory["screens"].keys()
    if not missing:
        return
    recovering = set()
    unidentified = set()
    for window in pending.values():
        checkpoints = window.get("checkpoints", {})
        cold_start = {}
        for name in missing.intersection(window["screens"]):
            if name not in checkpoints:
                unidentified.add(name)
                continue
            checkpoint = checkpoints[name]
            cold_start[name] = checkpoint
            if checkpoint.get("codex"):
                recovering.add(name)
            elif checkpoint.get("program"):
                unidentified.add(name)
        window["cold_start"] = cold_start
    if saved_boot_id and inventory.get("boot_id") != saved_boot_id:
        print("lap rebooted since the snapshot was saved.", flush=True)
    print(f"{len(missing)} saved Screen session(s) ended on lap. Opening replacements.", flush=True)
    if recovering:
        print(f"Reopening {len(recovering)} saved Codex conversation(s).", flush=True)
    if unidentified:
        print(f"{len(unidentified)} lost Screen session(s) have no supported work checkpoint. Opening shells.", flush=True)


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
        f"os_window_name {instance}\n{prepare_saved_session(window['session'], window.get('cold_start'))}\n"
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
        pending[instance] = dict(window)

    if not pending:
        print("The saved Kitty windows are already open.")
        return
    prepare_remote_recovery(pending, None if legacy else data.get("lap_boot_id"))

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
