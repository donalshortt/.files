#!/usr/bin/python3
"""Count live Codex sessions on this machine and configured SSH hosts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time


WAITING_FLAGS = {"waitingOnApproval", "waitingOnUserInput"}
CONTROL_SOCKET = "app-server-control/app-server-control.sock"
HANDSHAKE_TIMEOUT = 3
SSH_PROXY = (
    f'sock="${{CODEX_HOME:-$HOME/.codex}}/{CONTROL_SOCKET}"; '
    'test -S "$sock" && exec codex app-server proxy --sock "$sock"'
)


def excluded_thread(thread):
    if thread.get("ephemeral") or thread.get("archived") or thread.get("parentThreadId"):
        return True
    source = thread.get("source", "")
    if isinstance(source, str):
        return source.casefold().startswith("subagent")
    if isinstance(source, dict):
        return any(key.casefold().startswith("subagent") for key in source)
    return False


def classify_thread(thread):
    if excluded_thread(thread):
        return None
    status = thread.get("status") or {}
    kind = status.get("type")
    if kind == "active":
        return "waiting" if WAITING_FLAGS.intersection(status.get("activeFlags") or []) else "working"
    if kind in {"idle", "systemError"}:
        return "waiting"
    return None


def count_threads(threads):
    working = waiting = 0
    for thread in threads:
        state = classify_thread(thread)
        working += state == "working"
        waiting += state == "waiting"
    return working, waiting


def format_counts(working, waiting, label="Agents"):
    return f"{label}: {working} working | {waiting} waiting"


class Client:
    def __init__(self, path, timeout=HANDSHAKE_TIMEOUT):
        self.path = str(path)
        self.timeout = timeout
        self.connection = None
        self.request_id = 0
        self.excluded_ids = set()

    def close(self):
        if self.connection is not None:
            self.connection.close(timeout=0)
            self.connection = None
        self.excluded_ids.clear()

    def open_transport(self):
        transport = socket.socket(socket.AF_UNIX)
        transport.settimeout(self.timeout)
        try:
            transport.connect(self.path)
        except BaseException:
            transport.close()
            raise
        return transport

    def connect(self):
        # Import lazily so the classification helpers can run on their own.
        import websocket

        transport = self.open_transport()
        try:
            self.connection = websocket.create_connection(
                "ws://localhost/", socket=transport,
                timeout=self.timeout, suppress_origin=True,
            )
        except BaseException:
            transport.close()
            raise
        self.call("initialize", {
            "clientInfo": {"name": "polybar_agent_counts", "version": "1.0"},
        })
        self.connection.send(json.dumps({"method": "initialized", "params": {}}))

    def call(self, method, params):
        self.request_id += 1
        request_id = self.request_id
        self.connection.send(json.dumps({
            "id": request_id, "method": method, "params": params,
        }))
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex status request timed out")
            self.connection.settimeout(remaining)
            raw = self.connection.recv()
            if not raw:
                raise ConnectionError("Codex status connection closed")
            response = json.loads(raw)
            # Configuration warnings and lifecycle notifications may arrive
            # between RPC responses. Never treat them as a status snapshot.
            if "method" in response or response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError("Codex status request failed")
            return response["result"]

    def threads(self):
        if self.connection is None:
            self.connect()
        loaded = set(self.call("thread/loaded/list", {})["data"])
        self.excluded_ids.intersection_update(loaded)
        roots = []
        for thread_id in sorted(loaded - self.excluded_ids):
            try:
                thread = self.call("thread/read", {
                    "threadId": thread_id, "includeTurns": False,
                })["thread"]
            except RuntimeError:
                # A short-lived worker may close after the initial snapshot.
                # Ignore only confirmed departures; real API errors must still
                # produce unavailable rather than a misleading partial count.
                if thread_id not in self.call("thread/loaded/list", {})["data"]:
                    continue
                raise
            if excluded_thread(thread):
                # Archiving is reversible while a session remains loaded.
                if not thread.get("archived"):
                    self.excluded_ids.add(thread_id)
            else:
                roots.append(thread)
        return roots

    def counts(self):
        return count_threads(self.threads())


class SSHClient(Client):
    def __init__(self, host):
        super().__init__(path=None)
        self.host = host
        self.process = None

    def open_transport(self):
        # The Codex proxy passes the existing Unix socket's WebSocket bytes
        # through SSH stdio, so only the local machine needs websocket-client.
        transport, peer = socket.socketpair()
        try:
            with peer:
                transport.settimeout(self.timeout)
                self.process = subprocess.Popen(
                    ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2",
                     "-o", "StrictHostKeyChecking=yes", "-o", "ClearAllForwardings=yes",
                     "-o", "ForwardAgent=no", "-o", "ForwardX11=no", "-o", "PermitLocalCommand=no",
                     "-o", "ControlPath=none", "-o", "RemoteCommand=none",
                     "--", self.host, SSH_PROXY],
                    stdin=peer, stdout=peer, stderr=subprocess.DEVNULL,
                )
        except BaseException:
            transport.close()
            raise
        return transport

    def close(self):
        try:
            super().close()
        finally:
            if self.process is not None:
                process, self.process = self.process, None
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def configured_hosts():
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "polybar/agent-hosts"
    try:
        lines = config.read_text().splitlines()
    except FileNotFoundError:
        return ()

    hosts = []
    for number, line in enumerate(lines, start=1):
        host = line.partition("#")[0].strip()
        if not host or host in hosts:
            continue
        if re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", host):
            hosts.append(host)
        else:
            print(f"{config}:{number}: invalid SSH alias", file=sys.stderr)
    return tuple(hosts)


class Sources:
    def __init__(self, hosts=None):
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.clients = {None: Client(codex_home / CONTROL_SOCKET)}
        if hosts is None:
            hosts = configured_hosts()
        self.clients.update({host: SSHClient(host) for host in hosts})
        self.executor = (ThreadPoolExecutor(max_workers=len(self.clients))
                         if len(self.clients) > 1 else None)

    @staticmethod
    def read(client):
        try:
            return client.threads()
        except Exception:
            client.close()
            return None

    def snapshots(self):
        if self.executor is None:
            return {None: self.read(self.clients[None])}
        requests = {host: self.executor.submit(self.read, client)
                    for host, client in self.clients.items()}
        return {host: request.result() for host, request in requests.items()}

    def close(self):
        if self.executor is not None:
            self.executor.shutdown()
        for client in self.clients.values():
            client.close()


def snapshot_counts(snapshots):
    counts = {}
    for host, threads in snapshots.items():
        if threads is None:
            counts[host] = {"error": "unavailable"}
        else:
            working, waiting = count_threads(threads)
            counts[host] = {"working": working, "waiting": waiting}

    local = counts.pop(None)
    return {"local": local, "remote": counts} if counts else local


def format_snapshot(snapshots):
    counts = snapshot_counts(snapshots)
    if "remote" in counts:
        sources = [("local", counts["local"]), *counts["remote"].items()]
    else:
        sources = [("Agents", counts)]
    return "  ·  ".join(
        f"{label}: unavailable" if "error" in count else
        format_counts(count["working"], count["waiting"], label)
        for label, count in sources
    )


def notify_remote_ready(previous, current):
    ready = {}
    for host, threads in current.items():
        if host is None or not threads:
            continue
        previously_working = {thread["id"] for thread in previous.get(host) or ()
                              if classify_thread(thread) == "working"}
        waiting = [thread["id"] for thread in threads
                   if thread["id"] in previously_working and classify_thread(thread) == "waiting"]
        if waiting:
            ready[host] = waiting
    if not ready:
        return

    # Resolve the current local Kitty panes using the same matching as the picker.
    picker = Path(__file__).resolve().parents[2] / "rofi/agent-picker.py"
    payload = {"ready": ready, "threads": {host: current[host] for host in ready}}
    try:
        subprocess.run([sys.executable, "-B", str(picker), "--notify-ready"],
                       input=json.dumps(payload), text=True, timeout=8, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Could not mark remote agent attention: {error}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Refresh every two seconds")
    parser.add_argument("--json", action="store_true", help="Output counts as JSON")
    args = parser.parse_args(argv)
    try:
        sources = Sources()
    except (OSError, ValueError) as error:
        parser.error(str(error))

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    previous_output = None
    previous_snapshots = {}
    exit_code = 0
    try:
        while True:
            started = time.monotonic()
            snapshots = sources.snapshots()
            output = (json.dumps(snapshot_counts(snapshots)) if args.json
                      else format_snapshot(snapshots))
            exit_code = int(all(threads is None for threads in snapshots.values()))
            if output != previous_output or not args.watch:
                print(output, flush=True)
                previous_output = output
            if not args.watch:
                break
            notify_remote_ready(previous_snapshots, snapshots)
            previous_snapshots = snapshots
            time.sleep(max(0, 2 - (time.monotonic() - started)))
    except BrokenPipeError:
        # Avoid another flush into Polybar's closed pipe during interpreter exit.
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, sys.stdout.fileno())
        finally:
            os.close(devnull)
    except KeyboardInterrupt:
        pass
    finally:
        sources.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
