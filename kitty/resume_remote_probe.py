"""Inventory the remote Screen sessions named by a Kitty snapshot."""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import subprocess
from typing import NamedTuple


PROC = Path("/proc")
SESSION = r"resume-[0-9a-f]{32}"
SOCKET = re.compile(rf"\s*(\d+)\.({SESSION})\s+")
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
SHELLS = {"ash", "bash", "csh", "dash", "elvish", "fish", "ksh", "nu", "sh", "tcsh", "xonsh", "zsh"}


class Process(NamedTuple):
    pid: int
    parent: int
    group: int
    tty: int
    foreground: int
    name: str

    @property
    def path(self):
        return PROC / str(self.pid)

    def cwd(self):
        try:
            path = (self.path / "cwd").readlink()
            if path.is_absolute() and path.is_dir():
                return str(path)
        except OSError:
            pass
        return ""

    def argv(self):
        try:
            return os.fsdecode((self.path / "cmdline").read_bytes().rstrip(b"\0")).split("\0")
        except OSError:
            return []


def processes():
    result = {}
    for path in PROC.iterdir():
        try:
            if not path.name.isdecimal() or path.stat().st_uid != os.getuid():
                continue
            name, _, fields = (path / "stat").read_text().rpartition(")")
            state, parent, group, _, tty, foreground = fields.split()[:6]
            if state not in {"Z", "X"}:
                pid = int(path.name)
                result[pid] = Process(pid, int(parent), int(group), int(tty), int(foreground), name.partition("(")[2])
        except (OSError, ValueError):
            continue
    return result


def screen_servers(requested, owned):
    result = defaultdict(set)
    listed = False
    for executable in ("screen", str(Path.home() / ".local/bin/screen5")):
        try:
            listing = subprocess.run(
                [executable, "-ls"], text=True, encoding="utf-8", errors="replace",
                env=dict(os.environ, LC_ALL="C"), capture_output=True, timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        # Screen can exit nonzero for an empty socket directory. Confirm each
        # listed socket against a live Screen process owned by this user.
        if listing.returncode and not listing.stdout.lstrip().startswith("No Sockets found in "):
            continue
        listed = True
        for line in listing.stdout.splitlines():
            if match := SOCKET.match(line):
                pid, name = int(match[1]), match[2]
                process = owned.get(pid)
                if name in requested and process and process.name in {"screen", "screen5"}:
                    if re.search(r"\((?:Multi,\s*)?(?:Attached|Detached)\)\s*$", line):
                        result[name].add(pid)
    if not listed:
        raise RuntimeError("Could not list sessions with either Screen executable")
    return result


def root_rollout(path):
    try:
        with path.open() as rollout:
            event = json.loads(rollout.readline(1 << 20))
        payload = event["payload"]
        thread = payload["id"]
        cwd = payload["cwd"]
        source = payload.get("source")
        if (event["type"] == "session_meta" and UUID.fullmatch(thread) and Path(cwd).is_absolute()
                and not payload.get("parent_thread_id")
                and not any(label.startswith("subagent") for label in source_labels(source))):
            return thread, str(Path(cwd).resolve())
    except (OSError, KeyError, TypeError, ValueError):
        pass
    return None


def source_labels(source):
    if isinstance(source, dict):
        return {key.casefold() for key in source}
    return {source.casefold()} if isinstance(source, str) else set()


def loaded_rollouts(process):
    roots = set()
    try:
        for descriptor in (process.path / "fd").iterdir():
            try:
                target = descriptor.readlink()
                if target.name.startswith("rollout-") and target.suffix == ".jsonl" and descriptor.is_file():
                    if rollout := root_rollout(target):
                        roots.add(rollout)
            except OSError:
                continue
    except OSError:
        pass
    return roots


def foreground_conversation(process, cwd, children, codex_processes):
    argv, foreground_roots = codex_processes[process.pid]
    roots = set(foreground_roots)
    descendants = list(children[process.pid])
    visited = {process.pid}
    while descendants:
        child = descendants.pop()
        if child.pid in visited:
            continue
        visited.add(child.pid)
        descendants.extend(children[child.pid])
        if child.pid in codex_processes:
            child_argv, child_roots = codex_processes[child.pid]
            if "app-server" in child_argv and "--managed-daemon" not in child_argv:
                roots.update(child_roots)
    if roots:
        # A TUI can switch conversations after launch. Its private app
        # server's open rollout is stronger evidence than the initial argv.
        if len(roots) == 1:
            thread, workspace = roots.pop()
            if workspace == cwd:
                return thread
        return None

    explicit = {
        following for argument, following in zip(argv, argv[1:])
        if argument == "resume" and UUID.fullmatch(following)
    }
    if len(explicit) == 1:
        # The managed daemon serves multiple TUIs. Corroborate an explicit
        # resume ID only if it is the sole active rollout in this workspace
        # and the shared daemon still has that rollout open.
        active = set()
        shared = set()
        for backend_argv, backend_roots in codex_processes.values():
            matching = {thread for thread, workspace in backend_roots if workspace == cwd}
            active.update(matching)
            if "app-server" in backend_argv and "--managed-daemon" in backend_argv:
                shared.update(matching)
        if explicit == active == shared:
            return explicit.pop()
    return None


def foreground_process(group, owned):
    if len(group) == 1:
        return group[0]
    codex = [entry for entry in group if entry.name == "codex"]
    if len(codex) != 1:
        return None
    # On cold restore the login-shell wrapper and Codex share a group.
    ancestors = {codex[0].pid}
    parent = owned.get(codex[0].parent)
    while parent and parent.pid not in ancestors and parent.name in SHELLS and parent.tty == codex[0].tty:
        ancestors.add(parent.pid)
        parent = owned.get(parent.parent)
    if all(entry.pid in ancestors for entry in group):
        return codex[0]
    return None


def checkpoint(servers, owned):
    children = defaultdict(list)
    groups = defaultdict(list)
    for process in owned.values():
        children[process.parent].append(process)
        if process.tty and process.group == process.foreground:
            groups[(process.tty, process.group)].append(process)

    codex_processes = {
        process.pid: (process.argv(), loaded_rollouts(process))
        for process in owned.values() if process.name == "codex"
    }
    for name, pids in servers.items():
        windows = [process for pid in pids for process in children[pid] if process.tty]
        saved = {"cwd": "", "program": "", "codex": None}
        if not windows:
            saved["program"] = "unidentified Screen window"
        elif len(windows) > 1:
            saved["program"] = "multiple Screen windows"
        else:
            window = windows[0]
            foreground = groups[(window.tty, window.foreground)]
            process = foreground_process(foreground, owned)
            if not process:
                saved.update(cwd=window.cwd(), program="ambiguous foreground job")
            else:
                cwd = process.cwd()
                saved["cwd"] = cwd or window.cwd()
                if process.pid != window.pid or process.name not in SHELLS:
                    saved["program"] = process.name
                if process.name == "codex" and cwd:
                    saved["codex"] = foreground_conversation(process, cwd, children, codex_processes)
        yield name, saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="check session existence only")
    parser.add_argument("sessions", nargs="*")
    args = parser.parse_args()
    requested = set(args.sessions)
    if not all(re.fullmatch(SESSION, session) for session in requested):
        parser.error("invalid managed Screen session name")
    owned = processes()
    servers = screen_servers(requested, owned)
    screens = dict.fromkeys(servers, {}) if args.list else dict(checkpoint(servers, owned))
    print(json.dumps({"boot_id": (PROC / "sys/kernel/random/boot_id").read_text().strip(), "screens": screens}))


if __name__ == "__main__":
    main()
