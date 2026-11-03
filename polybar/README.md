Agent counter
=============

The centre bar displays `Agents: 8 working | 5 waiting`, refreshed every two
seconds from the local Codex app-server's live session status.

- Working: a top-level session running a turn, including tool execution.
- Waiting: an idle session ready for the next prompt, a session paused for input
  or approval, or a session reporting a system error that needs attention.
- Internal subagents, archived sessions, and unloaded history are excluded.

Focusing a terminal clears its desktop attention marker but does not change its
waiting status. The counter changes when the session starts work again.

The module is enabled only in `bar/centre` in the main, laptop basic, and laptop
WFH configurations. Laptop work has no centre bar, so it has no counter.

The collector uses `/usr/bin/python3` and the system `websocket-client` module.
It connects to `$CODEX_HOME/app-server-control/app-server-control.sock`, defaulting
to `~/.codex`. It reads status metadata without resuming sessions or loading turn
history. If the server cannot be reached, the display reads `Agents: unavailable`.

Inspect the current counts:

```sh
python3 -B polybar/scripts/agent-counts.py --json
```

Run the counter and desktop marker checks:

```sh
python3 -B -m unittest discover -s polybar/tests
```
