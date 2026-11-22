#!/usr/bin/python3
"""Pick an open Codex terminal using Rofi and live session status."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("agent_counts", ROOT / "polybar/scripts/agent-counts.py")
agent_counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_counts)

spec = importlib.util.spec_from_file_location("kitty_desktop", ROOT / "kitty/desktop.py")
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)
desktop_locations = desktop.desktop_locations
kitty_request = desktop.kitty_request
terminal_sources = desktop.terminal_sources


def clean_text(value):
    # Titles and paths are data, never Rofi markup, row options, or commands.
    return " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value or "")).split())


def canonical_cwd(value):
    return os.path.realpath(value) if value else None


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


def remote_title(title):
    task, separator, project = clean_text(title).rpartition(" | ")
    if not separator:
        return "", ""
    task = re.sub(r"^[\u2800-\u28ff\s]+", "", task)
    return re.sub(r"^(?:[●*] )?\[ [!.] \] Action Required \| ", "", task), project


def title_matches(value, displayed):
    if value == displayed:
        return True
    for suffix in ("...", "…"):
        if displayed.endswith(suffix):
            prefix = displayed.removesuffix(suffix)
            return bool(prefix) and value.startswith(prefix)
    return False


def remote_match(pane, threads):
    task, project = remote_title(pane.get("title"))
    if not task:
        return None
    matches = [index for index, thread in enumerate(threads)
               if title_matches(clean_text(Path(thread.get("cwd") or "/").name or "/"), project)]
    # Screen's ASCII spinner uses characters that can also start a real title.
    task_titles = (task, task[2:]) if re.match(r"^[|/\\-] ", task) else (task,)
    named = [index for index in matches
             if any(title_matches(clean_text(threads[index].get("name")), title) for title in task_titles)]
    if named:
        return named[0] if len(named) == 1 else None
    if len(matches) == 1 and not clean_text(threads[matches[0]].get("name")):
        return matches[0]
    return None


def build_remote_entries(host, threads, panes, locations):
    threads = [thread for thread in threads or [] if agent_counts.classify_thread(thread) is not None]
    matches = {}
    for pane, process in panes:
        index = remote_match(pane, threads)
        if index is not None:
            matches.setdefault(index, []).append((pane, process))

    entries = []
    for index, thread in enumerate(threads):
        cwd = thread.get("cwd") or ""
        entry = {"host": host, "desktop": None, "monitor": None, "cwd": cwd,
                 "thread_id": thread.get("id"), "status": agent_counts.classify_thread(thread),
                 "task": clean_text(thread.get("name")), "project": Path(cwd or "/").name or "/"}
        candidates = matches.get(index, [])
        if len(candidates) == 1:
            pane, process = candidates[0]
            entry.update(locations[pane["x11_id"]])
            entry.update({key: pane[key] for key in ("pane_id", "x11_id", "kitty_pid", "title")})
            entry["pid"] = process["pid"]
            if not entry["task"]:
                entry["task"] = remote_title(pane.get("title"))[0]
        entry["task"] = entry["task"] or "Codex"
        entries.append(entry)
    return entries


def build_entries(panes, threads, locations, remote_threads=None):
    entries = []
    remote_panes = {host: [] for host in remote_threads or {}}
    seen = set()
    for pane in panes:
        identity = (pane["kitty_pid"], pane["pane_id"])
        if identity in seen or not pane.get("processes") or pane["x11_id"] not in locations:
            continue
        seen.add(identity)
        processes = [process for process in pane["processes"]
                     if Path((process.get("cmdline") or [""])[0]).name == "codex"]
        if not processes:
            if len(pane["processes"]) == 1:
                process = pane["processes"][0]
                host = process.get("host")
                if host in remote_panes:
                    remote_panes[host].append((pane, process))
            continue
        thread = match_thread(pane, threads)
        status = agent_counts.classify_thread(thread) if thread else "unknown"
        title = clean_text(thread.get("name")) if thread else title_name(pane.get("title"))
        project = Path(pane.get("cwd") or "/").name or "/"
        entries.append({**pane, **locations[pane["x11_id"]],
                        "processes": processes, "pid": processes[0]["pid"],
                        "thread_id": thread.get("id") if thread else None,
                        "status": status, "task": title or "Codex", "project": project})
    for host, host_threads in (remote_threads or {}).items():
        entries.extend(build_remote_entries(host, host_threads, remote_panes[host], locations))
    order = {"waiting": 0, "working": 1, "unknown": 2}
    return sorted(entries, key=lambda entry: (order[entry["status"]], clean_text(entry["project"]).casefold(),
                                              entry["task"].casefold(), entry.get("host", ""),
                                              entry.get("pane_id", 0)))


def row_label(entry):
    desktop = f"Desktop {clean_text(entry['desktop'])}" if entry["desktop"] is not None else ""
    location = " / ".join(filter(None, (clean_text(entry.get("host")), desktop)))
    return "  |  ".join((entry["status"].capitalize(), location,
                          clean_text(entry["task"]), clean_text(entry["project"])))


def pane_inventory(sources, hosts):
    hosts = list(hosts)
    return [pane for source in sources.values()
            for pane in kitty_request(source, "inventory", hosts)["panes"]]


def collect_entries():
    sources = agent_counts.Sources()
    try:
        snapshots = sources.snapshots()
    finally:
        sources.close()
    threads = snapshots.get(None) or []
    remote_threads = {host: threads for host, threads in snapshots.items() if host is not None}
    panes = pane_inventory(terminal_sources(remote_threads), remote_threads)
    return build_entries(panes, threads, desktop_locations() if panes else {}, remote_threads)


def notify_ready(ready, threads):
    remote_threads = {host: threads[host] for host, identifiers in ready.items()
                      if identifiers and threads.get(host)}
    if not remote_threads:
        return
    sources = terminal_sources(remote_threads)
    panes = pane_inventory(sources, remote_threads)
    if not panes:
        return
    entries = build_entries(panes, [], desktop_locations(), remote_threads)
    targets = {}
    for entry in entries:
        if ("pane_id" in entry and entry["status"] == "waiting"
                and entry["thread_id"] in ready.get(entry.get("host"), ())):
            targets.setdefault(entry["kitty_pid"], []).append(entry_target(entry))
    for kitty_pid, panes_to_mark in targets.items():
        kitty_request(sources[kitty_pid], "attention", panes_to_mark)


def choose_entry(entries):
    urgent = ",".join(str(index) for index, entry in enumerate(entries) if entry["status"] == "waiting")
    arguments = ["rofi", "-dmenu", "-i", "-no-custom", "-no-sort", "-no-markup-rows", "-format", "i",
                 "-p", "Agents", "-columns", "1", "-lines", "12",
                 "-theme-str", "window { width: 85%; }",
                 "-mesg", "Waiting agents first. Enter to switch terminals, Esc to cancel."]
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


def entry_target(entry):
    target = {key: entry[key] for key in ("pane_id", "x11_id", "pid")}
    if entry.get("host"):
        target["title"] = entry["title"]
    return target


def activate_entry(entry):
    host = entry.get("host")
    if "pane_id" not in entry:
        raise RuntimeError(f"No matching local Kitty pane for this agent on {host}.")
    source = terminal_sources((host,) if host else ()).get(entry["kitty_pid"])
    if source is None:
        raise RuntimeError("That agent's terminal has closed. Open the picker again.")
    response = kitty_request(source, "focus", entry_target(entry))
    if response.get("ok") is not True:
        raise RuntimeError("Kitty could not select that agent")
    # This path runs only after the user selects an entry in Rofi.
    subprocess.run(["bspc", "node", hex(entry["x11_id"]), "-f"], check=True, timeout=3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Print rows without opening Rofi or switching focus")
    parser.add_argument("--json", action="store_true", help="Print entries without opening Rofi or switching focus")
    parser.add_argument("--notify-ready", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.notify_ready:
            payload = json.load(sys.stdin)
            notify_ready(payload["ready"], payload["threads"])
            return 0
        entries = collect_entries()
        if args.json:
            print(json.dumps(entries))
        elif args.list:
            print("\n".join(row_label(entry) for entry in entries))
        elif not entries:
            subprocess.run(["rofi", "-e", "No live Codex agents found."], check=False)
        else:
            selected = choose_entry(entries)
            if selected is not None:
                activate_entry(selected)
    except Exception as error:
        message = f"Agent picker: {clean_text(error)}"
        if args.list or args.json or args.notify_ready:
            print(message, file=sys.stderr)
        else:
            subprocess.run(["rofi", "-e", message], check=False)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
