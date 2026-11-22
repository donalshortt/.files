"""Query Kitty, its running terminal processes, and bspwm desktop assignments."""

import getopt
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile


AGENT_PICKER_KITTEN = Path(__file__).resolve().with_name("agent_picker.py")


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


def ssh_destination(command):
    if not command or Path(command[0]).name != "ssh":
        return None
    # Accept SSH options that preserve the destination configured for the
    # alias. An alternate user, port, or configuration needs its own alias.
    try:
        _, arguments = getopt.getopt(command[1:], "46AaCc:D:e:i:J:kKL:m:qR:tTXxY")
    except getopt.GetoptError:
        return None
    return arguments[0] if arguments else None


def terminal_sources(hosts=(), *, include_all=False):
    """Find one output stream per Kitty instance with a matching process."""
    sources = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            if not include_all:
                command = [os.fsdecode(arg) for arg in (proc / "cmdline").read_bytes().split(b"\0")]
                if Path(command[0]).name != "codex" and ssh_destination(command) not in hosts:
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


def kitty_request(source, action, target=None, *, kitten=AGENT_PICKER_KITTEN):
    # This is Kitty's terminal OUTPUT protocol. Never read the terminal or send
    # a response to the foreground application's input stream.
    # Titles can mirror a shell command. Keep the reply in memory and use the
    # owner-only directory to restrict who can connect to the reply socket.
    with tempfile.TemporaryDirectory(prefix="kitty-", dir="/tmp") as directory, socket.socket(socket.AF_UNIX) as listener:
        address = os.path.join(directory, "reply.sock")
        listener.bind(address)
        listener.listen(1)
        listener.settimeout(4)
        arguments = [address, action]
        if target is not None:
            arguments.append(json.dumps(target))
        command = {
            "cmd": "kitten", "version": kitty_version(), "no_response": True,
            "payload": {"kitten": str(kitten),
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
        try:
            connection, _ = listener.accept()
            with connection, connection.makefile("rb") as stream:
                connection.settimeout(4)
                response = json.load(stream)
        except TimeoutError as error:
            raise RuntimeError(f"Kitty did not answer {Path(kitten).name}") from error
        if "error" in response:
            raise RuntimeError(response["error"])
        return response


def desktop_locations(*, include_details=False):
    state = json.loads(subprocess.check_output(["bspc", "wm", "-d"], text=True, timeout=3))
    locations = {}

    def walk(node, desktop, monitor):
        if not node:
            return
        client = node.get("client")
        if client is not None:
            location = {"desktop": desktop["name"], "monitor": monitor}
            if include_details:
                location.update(instance=client.get("instanceName", ""), desktop_id=desktop["id"])
            locations[node["id"]] = location
        walk(node.get("firstChild"), desktop, monitor)
        walk(node.get("secondChild"), desktop, monitor)

    for monitor in state["monitors"]:
        for desktop in monitor["desktops"]:
            walk(desktop.get("root"), desktop, monitor["name"])
    return locations
