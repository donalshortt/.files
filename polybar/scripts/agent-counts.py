#!/usr/bin/python3
"""Count live Codex sessions through the local app-server's read-only API."""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time


WAITING_FLAGS = {"waitingOnApproval", "waitingOnUserInput"}


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


def format_counts(working, waiting):
    return f"Agents: {working} working | {waiting} waiting"


class Client:
    def __init__(self, path, timeout=3):
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

    def connect(self):
        # websocket-client is provided by the system Python; importing lazily
        # keeps the classification helpers usable without a running daemon.
        import websocket

        transport = socket.socket(socket.AF_UNIX)
        transport.settimeout(self.timeout)
        try:
            transport.connect(self.path)
            self.connection = websocket.create_connection(
                "ws://localhost/", socket=transport,
                timeout=self.timeout, suppress_origin=True,
            )
        except Exception:
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

    def counts(self):
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
        return count_threads(roots)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Refresh every two seconds")
    parser.add_argument("--json", action="store_true", help="Output counts as JSON")
    args = parser.parse_args(argv)
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    client = Client(codex_home / "app-server-control" / "app-server-control.sock")

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    previous = None
    exit_code = 0
    try:
        while True:
            started = time.monotonic()
            try:
                working, waiting = client.counts()
                output = json.dumps({"working": working, "waiting": waiting}) if args.json else format_counts(working, waiting)
                exit_code = 0
            except Exception:
                client.close()
                output = json.dumps({"error": "unavailable"}) if args.json else "Agents: unavailable"
                exit_code = 1
            if output != previous or not args.watch:
                print(output, flush=True)
                previous = output
            if not args.watch:
                break
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
        client.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
