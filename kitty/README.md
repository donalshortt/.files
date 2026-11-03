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

Check Polybar's actual output for hidden and visible urgent desktops:

```sh
python3 -B -m unittest discover -s polybar/tests
```

The test uses a fake bspwm socket and Polybar's stdout mode. It queries the
existing display's monitors but creates no windows and changes no desktop state.
