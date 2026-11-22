Agent picker
============

Press **Super+X**, or click the agent counter on the centre Polybar, to open the
picker. It uses the existing Rofi theme with one column of live agents.

Each row shows status, desktop, task, and project. Waiting agents appear first.
Type to search, press Enter to switch to the selected terminal and Kitty tab,
or Escape to cancel. The list is a snapshot taken when the picker opens.

The picker shares the counter's live Codex status reader and excludes internal
subagents. It identifies terminals by their Kitty pane and process IDs, so
agents on the same desktop or in separate tabs remain distinct. A closed or
changed target is rejected before switching desktops.

Local status is matched by working directory and, when necessary, current task title.
If the status service is unavailable or the match is ambiguous, a terminal is
shown as Unknown and can still be selected. The original process's `resume`
argument is not used to guess which task is currently selected.

Agents on [configured SSH hosts](../polybar/README.md) show their host alias.
The picker can switch to an existing local Kitty tab opened through that alias
when its task title and project identify one live session. Rows without a
matching pane still show the agent's status.

Inspect the picker without opening a menu or changing focus:

```sh
/usr/bin/python3 -B rofi/agent-picker.py --list
/usr/bin/python3 -B rofi/agent-picker.py --json
```

The picker requires the existing Rofi, Kitty remote control, bspwm, and agent
counter dependencies. It loads `kitty/agent_picker.py` through Kitty's no-UI
extension API; no extra Kitty symlink or terminal restart is needed.

Run the routing and cancellation checks with desktop APIs mocked:

```sh
python3 -B -m unittest discover -s rofi/tests
```
