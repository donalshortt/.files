Codex desktop attention
======================

`notifications.py` preserves Kitty popups and marks the emitting Codex terminal
window urgent. Polybar displays a red `!` on its desktop, including on unfocused
monitors. bspwm clears the marker when that terminal window receives focus.

Install on another machine alongside the existing `kitty.conf` symlink:

```sh
ln -s ~/.files/kitty/notifications.py ~/.config/kitty/notifications.py
```

Kitty loads the handler on startup. To reload it in an existing Kitty instance,
run this from a shell inside that instance:

```sh
kitten @ kitten ~/.files/kitty/reload_notifications.py
```

This uses Kitty's configured remote control and opens no overlay. The marker
means unread agent activity; it does not distinguish a finished reply from a
question. Urgency belongs to the OS window, so a hidden Kitty tab inside an
already focused OS window cannot highlight that desktop independently.

For [configured SSH hosts](../polybar/README.md), the Polybar counter also
requests attention when an agent changes from working to waiting and the
picker can identify its local Kitty pane. This uses the live status feed, so
it works even when the terminal notification is swallowed by a multiplexer.

Check Polybar's actual output for hidden and visible urgent desktops:

```sh
python3 -B -m unittest discover -s polybar/tests
```

The test uses a fake bspwm socket and Polybar's stdout mode. It queries the
existing display's monitors but creates no windows and changes no desktop state.

Saving terminals before shutdown
================================

`sd` saves Kitty windows on their bspwm desktops, including tabs, splits, working
directories, and terminal output. Run `resume` after signing back in to reopen
the saved layout. The snapshot lives in `${XDG_STATE_HOME:-~/.local/state}/kitty-resume/`
and is readable only by your user.

Interactive `ssh lap` logins started from Kitty use GNU Screen on `lap`. Their
remote shells and jobs continue while this machine is off. Running `tt` on
`lap` opens a managed Screen session in a new Kitty tab at the current remote
directory. Older plain `lap` logins reopened by `resume` get new Screen sessions.
When the saved login includes a remote working directory, the new session
starts there.

If `lap` powers off, its running Screen sessions end. A new save records the
remote working directory and the exact saved Codex conversation when it can
identify one. `resume` reattaches surviving Screen sessions and uses those
checkpoints to reopen conversations in replacement sessions. Older snapshots
and programs without a supported checkpoint reopen as shells with saved
terminal output.

If a plain SSH login is open, `sd` saves the layout and output, prints the
affected desktops, and stops before shutdown. `sd --force` shuts down after
saving that context. Local jobs can exit during shutdown. Their panes reopen
with a shell in the saved working directory and the saved terminal output.
Run `source ~/.zsh_aliases` in an existing shell to load the new option.
