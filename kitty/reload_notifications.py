"""Reload the notification hook in a running Kitty without opening any UI.

Usage: kitten @ kitten ~/.files/kitty/reload_notifications.py
"""

import runpy
from pathlib import Path

from kittens.tui.handler import result_handler
from kitty.constants import config_dir


def main(args):
    pass


@result_handler(no_ui=True)
def handle_result(args, result, target_window_id, boss):
    handler_path = Path(config_dir) / "notifications.py"
    handler = runpy.run_path(str(handler_path))["main"]
    boss.notification_manager.filter_script = handler
    # A caller using no_response can request an acknowledgement on disk instead
    # of having Kitty write a remote-control response into a running agent.
    if len(args) > 1:
        Path(args[1]).write_text("loaded\n")
    return True
