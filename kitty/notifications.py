"""Keep Codex desktop notifications and mark their Kitty window urgent."""

from os.path import basename

from kitty.fast_data_types import get_boss, request_attention
from kitty.utils import log_error


def main(notification):
    # Returning False preserves Kitty's normal popup and notification actions.
    # Use the emitting pane, never the currently active terminal or desktop.
    try:
        window = get_boss().window_id_map.get(notification.channel_id)
        if window is None or window.destroyed or window.is_focused:
            return False

        is_codex = notification.application_name.casefold() == "codex"
        if not is_codex:
            is_codex = any(
                basename((process.get("cmdline") or [""])[0]) == "codex"
                for process in window.child.foreground_processes
            )
        if is_codex:
            # bspwm clears this native urgency hint when the OS window is focused.
            # This neither rings the bell nor changes focus.
            request_attention(window.os_window_id)
    except Exception as error:
        # A failed attention hint must never prevent the original notification.
        log_error("Codex desktop attention failed:", error)
    return False
