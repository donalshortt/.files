"""Check agent counts using the live API's thread/status shapes."""

import importlib.util
import json
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent-counts.py"


def load_counter():
    spec = importlib.util.spec_from_file_location("agent_counts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counter = load_counter()

    def test_counts_sessions_without_inflating_counts_with_subagents(self):
        # Current TUI sessions use source="vscode" even when run in Kitty.
        # One working parent can have many idle or active internal subagents.
        threads = [
            {"id": "parent", "source": "vscode", "status": {"type": "active", "activeFlags": []}},
            {"id": "cli", "source": "cli", "status": {"type": "active", "activeFlags": []}},
            {"id": "reply", "source": "vscode", "status": {"type": "idle"}},
            {"id": "approval", "source": "vscode", "status": {"type": "active", "activeFlags": ["waitingOnApproval"]}},
            {"id": "question", "source": "vscode", "status": {"type": "active", "activeFlags": ["waitingOnUserInput"]}},
            {"id": "error", "source": "vscode", "status": {"type": "systemError"}},
            {"id": "worker", "source": {"subAgent": {"thread_spawn": {"parent_thread_id": "parent", "depth": 1}}}, "status": {"type": "active", "activeFlags": []}},
            {"id": "idle-worker", "source": {"subAgent": {"thread_spawn": {"parent_thread_id": "parent", "depth": 1}}}, "status": {"type": "idle"}},
            {"id": "review-worker", "source": "subAgentReview", "status": {"type": "idle"}},
            {"id": "closed", "source": "vscode", "status": {"type": "notLoaded"}},
            {"id": "ephemeral", "source": "vscode", "ephemeral": True, "status": {"type": "active", "activeFlags": []}},
            {"id": "archived", "source": "vscode", "archived": True, "status": {"type": "idle"}},
        ]
        self.assertEqual(self.counter.count_threads(threads), (2, 4))

    def test_status_changes_move_one_session_between_working_and_waiting(self):
        thread = {"id": "session", "source": "vscode", "status": {"type": "active", "activeFlags": []}}
        self.assertEqual(self.counter.count_threads([thread]), (1, 0))
        thread["status"] = {"type": "active", "activeFlags": ["waitingOnUserInput"]}
        self.assertEqual(self.counter.count_threads([thread]), (0, 1))
        thread["status"] = {"type": "active", "activeFlags": []}
        self.assertEqual(self.counter.count_threads([thread]), (1, 0))
        thread["status"] = {"type": "idle"}
        self.assertEqual(self.counter.count_threads([thread]), (0, 1))
        thread["status"] = {"type": "notLoaded"}
        self.assertEqual(self.counter.count_threads([thread]), (0, 0))

    def test_empty_server_is_a_valid_zero_count(self):
        self.assertEqual(self.counter.count_threads([]), (0, 0))
        self.assertEqual(self.counter.format_counts(0, 0), "Agents: 0 working | 0 waiting")

    def test_session_closing_during_snapshot_does_not_hide_other_counts(self):
        client = self.counter.Client("unused.sock")
        client.connection = object()
        requests = []

        def call(method, params):
            requests.append((method, params))
            if method == "thread/loaded/list":
                loaded = ["parent", "gone"] if len(requests) == 1 else ["parent"]
                return {"data": loaded}
            if params["threadId"] == "gone":
                raise RuntimeError("Thread unloaded before it could be read")
            return {"thread": {"id": "parent", "source": "vscode", "status": {"type": "active", "activeFlags": []}}}

        client.call = call
        self.assertEqual(client.counts(), (1, 0))

    def test_read_failure_for_a_still_loaded_session_is_not_reported_as_zero(self):
        client = self.counter.Client("unused.sock")
        client.connection = object()

        def call(method, params):
            if method == "thread/loaded/list":
                return {"data": ["parent"]}
            raise RuntimeError("Status temporarily unavailable")

        client.call = call
        with self.assertRaises(RuntimeError):
            client.counts()

    def test_rpc_ignores_notifications_and_server_requests(self):
        # Server-initiated requests have their own id space and can collide
        # with our id. They must never be mistaken for our status response.
        messages = iter([
            {"method": "configWarning", "params": {}},
            {"id": 1, "method": "item/tool/requestUserInput", "params": {}},
            {"id": 1, "result": {"data": []}},
        ])

        class Connection:
            def send(self, raw):
                self.request = json.loads(raw)

            def settimeout(self, timeout):
                pass

            def recv(self):
                return json.dumps(next(messages))

        client = self.counter.Client("unused.sock")
        client.connection = Connection()
        self.assertEqual(client.call("thread/loaded/list", {}), {"data": []})


if __name__ == "__main__":
    unittest.main()
