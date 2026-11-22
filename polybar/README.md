Agent counter
=============

The centre bar refreshes live Codex counts every two seconds. With SSH hosts
configured, each machine has its own count, for example
`local: 2 working | 1 waiting  ·  lap: 1 working | 3 waiting`.

Click the counter, or press **Super+X**, to open the [agent picker](../rofi/README.md).

- Working: a top-level session running a turn, including tool execution.
- Waiting: an idle session ready for the next prompt, a session paused for input
  or approval, or a session reporting a system error that needs attention.
- Internal subagents, archived sessions, and unloaded history are excluded.

Focusing a terminal clears its desktop attention marker but does not change its
waiting status. The counter changes when the session starts work again.

The module is enabled only in `bar/centre` in the main, laptop basic, and laptop
WFH configurations. Laptop work has no centre bar, so it has no counter.

The collector uses `/usr/bin/python3` and the system `websocket-client` module.
It reads status metadata from `$CODEX_HOME/app-server-control/app-server-control.sock`
with `~/.codex` as the default Codex home.

Add one SSH alias per line to `${XDG_CONFIG_HOME:-$HOME/.config}/polybar/agent-hosts`
on the machine displaying the bar. For example, a line containing `lap` adds
that host to the counter and picker. Each alias needs an already trusted host
key and working non-interactive SSH authentication. The remote host needs
`codex app-server proxy` on its SSH command path and a running Codex app server.
Restart the bar after changing the host list. When a machine's status service
cannot be reached, its count displays `unavailable`.

Inspect the current counts:

```sh
/usr/bin/python3 -B polybar/scripts/agent-counts.py --json
```

Run the counter and desktop marker checks:

```sh
python3 -B -m unittest discover -s polybar/tests
```
