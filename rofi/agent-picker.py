#!/usr/bin/python3
"""Pick an open Codex terminal using Rofi and live session status."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("agent_counts", ROOT / "polybar/scripts/agent-counts.py")
agent_counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_counts)


def clean_text(value):
    # Titles and paths are data, never Rofi markup, row options, or commands.
    return " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value or "")).split())


def canonical_cwd(value):
    return os.path.realpath(value) if value else None


def kitty_parent(pid):
    for _ in range(12):
        proc = Path("/proc") / str(pid)
        try:
            command = (proc / "cmdline").read_bytes().split(b"\0")
            if command and Path(os.fsdecode(command[0])).name == "kitty":
                return pid
            fields = (proc / "status").read_text().splitlines()
            pid = int(next(line.split()[1] for line in fields if line.startswith("PPid:")))
        except (OSError, ValueError, StopIteration):
            return None
        if pid <= 1:
            return None
    return None


def terminal_sources():
    """Find one usable output stream per running Kitty instance."""
    sources = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            command = (proc / "cmdline").read_bytes().split(b"\0")
            if not command or Path(os.fsdecode(command[0])).name != "codex":
                continue
            terminal = os.readlink(proc / "fd/1")
            if not re.fullmatch(r"/dev/pts/\d+", terminal):
                continue
            # Read only the identifying environment key; never retain secrets.
            pane_id = next((entry.partition(b"=")[2] for entry in (proc / "environ").read_bytes().split(b"\0")
                            if entry.startswith(b"KITTY_WINDOW_ID=")), None)
            if pane_id is None:
                continue
            parent = kitty_parent(int(proc.name))
            if parent is not None:
                sources.setdefault(parent, {"kitty_pid": parent, "pane_id": int(pane_id), "terminal": terminal})
        except (OSError, ValueError):
            continue
    return sources


def kitty_version():
    version = subprocess.check_output(["kitty", "--version"], text=True, timeout=3)
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", version)
    if match is None:
        raise RuntimeError("Could not determine the Kitty remote-control version")
    return [int(part) for part in match.groups()]


def kitty_request(source, action, target=None):
    # This is Kitty's terminal OUTPUT protocol. Never read the terminal or send
    # a response to the foreground application's input stream.
    with tempfile.TemporaryDirectory(prefix="codex-agent-picker-") as directory:
        response_path = Path(directory) / "response.json"
        arguments = [str(response_path), action]
        if target is not None:
            arguments.append(json.dumps(target))
        command = {
            "cmd": "kitten", "version": kitty_version(), "no_response": True,
            "payload": {"kitten": str(ROOT / "kitty/agent_picker.py"),
                        "args": arguments, "match": f"id:{source['pane_id']}"},
        }
        packet = b"\x1bP@kitty-cmd" + json.dumps(command).encode("ascii") + b"\x1b\\"
        descriptor = os.open(source["terminal"], os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            if not stat.S_ISCHR(os.fstat(descriptor).st_mode):
                raise RuntimeError("Kitty output stream is no longer a terminal")
            if os.write(descriptor, packet) != len(packet):
                raise RuntimeError("Could not send the complete Kitty request")
        finally:
            os.close(descriptor)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            try:
                response = json.loads(response_path.read_text())
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response
            except FileNotFoundError:
                time.sleep(0.02)
        raise RuntimeError("Kitty did not answer the agent picker")


def desktop_locations():
    state = json.loads(subprocess.check_output(["bspc", "wm", "-d"], text=True, timeout=3))
    locations = {}

    def walk(node, desktop, monitor):
        if not node:
            return
        if node.get("client") is not None:
            locations[node["id"]] = {"desktop": desktop, "monitor": monitor}
        walk(node.get("firstChild"), desktop, monitor)
        walk(node.get("secondChild"), desktop, monitor)

    for monitor in state["monitors"]:
        for desktop in monitor["desktops"]:
            walk(desktop.get("root"), desktop["name"], monitor["name"])
    return locations


def title_name(title):
    name = clean_text(title).split(" | ", 1)[0]
    return re.sub(r"^[\u2800-\u28ff\s]+", "", name)


def match_thread(pane, threads):
    if not pane.get("cwd"):
        return None
    candidates = [thread for thread in threads
                  if agent_counts.classify_thread(thread) is not None
                  and canonical_cwd(thread.get("cwd")) == canonical_cwd(pane.get("cwd"))]
    if len(candidates) == 1:
        return candidates[0]
    name = title_name(pane.get("title"))
    named = [thread for thread in candidates if clean_text(thread.get("name")) == name]
    # A process's original `resume` argument may refer to a previously selected
    # task. Ambiguous status is shown as unknown rather than attributed wrongly.
    return named[0] if len(named) == 1 else None


def build_entries(panes, threads, locations):
    entries = []
    seen = set()
    for pane in panes:
        identity = (pane["kitty_pid"], pane["pane_id"])
        if identity in seen or not pane.get("processes") or pane["x11_id"] not in locations:
            continue
        seen.add(identity)
        thread = match_thread(pane, threads)
        status = agent_counts.classify_thread(thread) if thread else "unknown"
        title = clean_text(thread.get("name")) if thread else title_name(pane.get("title"))
        project = Path(pane.get("cwd") or "/").name or "/"
        entries.append({**pane, **locations[pane["x11_id"]],
                        "pid": pane["processes"][0]["pid"],
                        "thread_id": thread.get("id") if thread else None,
                        "status": status, "task": title or "Codex", "project": project})
    order = {"waiting": 0, "working": 1, "unknown": 2}
    return sorted(entries, key=lambda entry: (order[entry["status"]], clean_text(entry["project"]).casefold(), entry["task"].casefold(), entry["pane_id"]))


def row_label(entry):
    return "  |  ".join((entry["status"].capitalize(), f"Desktop {clean_text(entry['desktop'])}",
                          clean_text(entry["task"]), clean_text(entry["project"])))


def collect_entries():
    panes = []
    for source in terminal_sources().values():
        panes.extend(kitty_request(source, "inventory")["panes"])
    if not panes:
        return []
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    client = agent_counts.Client(codex_home / "app-server-control/app-server-control.sock")
    try:
        threads = client.threads()
    except Exception:
        # Navigation remains available when the status server is offline.
        threads = []
    finally:
        client.close()
    return build_entries(panes, threads, desktop_locations())


def choose_entry(entries):
    urgent = ",".join(str(index) for index, entry in enumerate(entries) if entry["status"] == "waiting")
    arguments = ["rofi", "-dmenu", "-i", "-no-custom", "-no-sort", "-no-markup-rows", "-format", "i",
                 "-p", "Agents", "-columns", "1", "-lines", "12",
                 "-theme-str", "window { width: 85%; }",
                 "-mesg", "Waiting agents first. Enter to switch; Esc to cancel."]
    if urgent:
        arguments.extend(["-u", urgent])
    result = subprocess.run(arguments, input="\n".join(row_label(entry) for entry in entries) + "\n",
                            text=True, capture_output=True)
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise RuntimeError("Rofi could not open the agent picker")
    try:
        index = int(result.stdout.strip())
        if 0 <= index < len(entries):
            return entries[index]
    except ValueError:
        pass
    raise RuntimeError("Rofi returned an invalid agent selection")


def activate_entry(entry):
    source = terminal_sources().get(entry["kitty_pid"])
    if source is None:
        raise RuntimeError("That agent's terminal has closed. Open the picker again.")
    target = {key: entry[key] for key in ("pane_id", "x11_id", "pid")}
    response = kitty_request(source, "focus", target)
    if response.get("ok") is not True:
        raise RuntimeError("Kitty could not select that agent")
    # This path runs only after the user selects an entry in Rofi.
    subprocess.run(["bspc", "node", hex(entry["x11_id"]), "-f"], check=True, timeout=3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Print rows without opening Rofi or switching focus")
    parser.add_argument("--json", action="store_true", help="Print entries without opening Rofi or switching focus")
    args = parser.parse_args(argv)
    try:
        entries = collect_entries()
        if args.json:
            print(json.dumps(entries))
        elif args.list:
            print("\n".join(row_label(entry) for entry in entries))
        elif not entries:
            subprocess.run(["rofi", "-e", "No open Codex terminals were found in Kitty."], check=False)
        else:
            selected = choose_entry(entries)
            if selected is not None:
                activate_entry(selected)
    except Exception as error:
        message = f"Agent picker: {clean_text(error)}"
        if args.list or args.json:
            print(message, file=sys.stderr)
        else:
            subprocess.run(["rofi", "-e", message], check=False)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
