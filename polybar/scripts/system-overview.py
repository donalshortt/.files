#!/usr/bin/env python3
import argparse
import ctypes
import json
import subprocess
from contextlib import contextmanager

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk


VISIBLE_ROWS = 12
WINDOW_PADDING = 10
CPU_REFRESH_MS = 500
X_GENERIC_EVENT = 35
XI_ALL_MASTER_DEVICES = 1
XI_RAW_BUTTON_PRESS = 15
POPUP_STYLE = b"""
window.system-overview {
    background-color: #2d303b;
    color: #c4cbd4;
    font: 11pt 'Iosevka Term';
}
"""


class XIEventMask(ctypes.Structure):
    _fields_ = [
        ("device_id", ctypes.c_int),
        ("length", ctypes.c_int),
        ("mask", ctypes.POINTER(ctypes.c_ubyte)),
    ]


@contextmanager
def observe_button_presses(on_press):
    # XInput2 gives us a copy of each press without grabbing or replaying it.
    x11 = ctypes.CDLL("libX11.so.6")
    xi = ctypes.CDLL("libXi.so.6")
    display_type = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = display_type
    x11.XDefaultRootWindow.argtypes = [display_type]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XConnectionNumber.argtypes = [display_type]
    x11.XPending.argtypes = [display_type]
    x11.XSync.argtypes = [display_type, ctypes.c_int]
    x11.XNextEvent.argtypes = [display_type, ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [display_type]
    xi.XIQueryVersion.argtypes = [display_type, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    xi.XISelectEvents.argtypes = [display_type, ctypes.c_ulong, ctypes.POINTER(XIEventMask), ctypes.c_int]

    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("Could not open the X display")
    try:
        major, minor = ctypes.c_int(2), ctypes.c_int(2)
        if xi.XIQueryVersion(display, ctypes.byref(major), ctypes.byref(minor)):
            raise RuntimeError("Could not initialize XInput2")
        mask = (ctypes.c_ubyte * (XI_RAW_BUTTON_PRESS // 8 + 1))()
        mask[XI_RAW_BUTTON_PRESS // 8] = 1 << (XI_RAW_BUTTON_PRESS % 8)
        selection = XIEventMask(XI_ALL_MASTER_DEVICES, len(mask), mask)
        root = x11.XDefaultRootWindow(display)
        if xi.XISelectEvents(display, root, ctypes.byref(selection), 1):
            raise RuntimeError("Could not observe XInput2 button presses")
        x11.XSync(display, False)

        def process_events(_fd, _condition):
            event = (ctypes.c_long * 24)()  # An XEvent union.
            while x11.XPending(display):
                x11.XNextEvent(display, event)
                if ctypes.c_int.from_buffer(event).value == X_GENERIC_EVENT and on_press():
                    break
            return GLib.SOURCE_CONTINUE

        source = GLib.io_add_watch(
            x11.XConnectionNumber(display), GLib.PRIORITY_DEFAULT, GLib.IO_IN, process_events,
        )
        try:
            yield
        finally:
            GLib.source_remove(source)
    finally:
        x11.XCloseDisplay(display)


def show_popup(heading, rows, pointer, monitor, click_x, refresh_rows=None):
    window = Gtk.Window(type=Gtk.WindowType.POPUP, title="System overview")
    window.set_accept_focus(False)
    window.set_border_width(WINDOW_PADDING)
    window.get_style_context().add_class("system-overview")
    style = Gtk.CssProvider()
    style.load_from_data(POPUP_STYLE)
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    window.add(content)
    title = Gtk.Label(xalign=0)
    title.set_markup(heading)
    title.set_line_wrap(True)
    content.pack_start(title, False, False, 0)
    body = Gtk.Label(label="\n".join(rows), xalign=0, yalign=0)
    scroll = Gtk.ScrolledWindow(propagate_natural_width=True, propagate_natural_height=True)
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.set_overlay_scrolling(False)
    scroll.add(body)
    content.pack_start(scroll, True, True, 0)
    content.show_all()
    scroll.set_max_content_width(monitor.width - 2 * WINDOW_PADDING)
    _, body_height = body.get_layout().get_pixel_size()
    if len(rows) > VISIBLE_ROWS:
        scroll.set_max_content_height(body_height * VISIBLE_ROWS // len(rows))

    width = content.get_preferred_width()[1] + 2 * WINDOW_PADDING
    left = min(max(click_x - width // 2, monitor.x), monitor.x + monitor.width - width)
    window.move(left, monitor.y + 36)

    loop = GLib.MainLoop()
    window.connect("destroy", lambda _window: loop.quit())

    def dismiss_if_outside():
        _, pointer_x, pointer_y = pointer.get_position()
        x, y = window.get_position()
        width, height = window.get_size()
        if x <= pointer_x < x + width and y <= pointer_y < y + height:
            return False
        window.destroy()
        return True

    def update_rows():
        try:
            text = "\n".join(refresh_rows())
        except (OSError, ValueError):
            text = "Usage data is unavailable"
        body.set_text(text)
        return GLib.SOURCE_CONTINUE

    with observe_button_presses(dismiss_if_outside):
        window.show()
        timer = GLib.timeout_add(CPU_REFRESH_MS, update_rows) if refresh_rows is not None else None
        try:
            loop.run()
        finally:
            if timer is not None:
                GLib.source_remove(timer)


def format_disk_size(size):
    if size is None:
        return "—"
    for unit in "BKMGTPE":
        if size < 1024 or unit == "E":
            return f"{size:.1f}".removesuffix(".0") + unit
        size /= 1024


def disk_overview():
    result = subprocess.run(
        ["lsblk", "--bytes", "--json", "--list", "--exclude", "7", "--output",
         "NAME,TYPE,SIZE,FSSIZE,FSUSED,FSAVAIL,MOUNTPOINT"],
        capture_output=True, text=True, check=True, timeout=5,
    )
    volumes = [("Device", "Size", "Used", "Used %", "Free", "Mount / status")]
    for device in json.loads(result.stdout)["blockdevices"]:
        mount = device["mountpoint"]
        if mount:
            status = "".join(char if char.isprintable() else " " for char in mount)
        else:
            status = "Disk" if device["type"] == "disk" else "Unmounted"
        used, free = device["fsused"], device["fsavail"]
        percent = "—"
        if used is not None and free is not None and used + free > 0:
            # Like Polybar, exclude filesystem space reserved from normal use.
            percent = f"{int(100 * used / (used + free) + 0.5)}%"
        volumes.append((
            device["name"], format_disk_size(device["fssize"] or device["size"]),
            format_disk_size(used), percent, format_disk_size(free), status,
        ))
    name_width, size_width, used_width, percent_width, free_width, _ = (
        max(map(len, column)) for column in zip(*volumes)
    )
    header, *rows = [
        f"{name:<{name_width}}  {size:>{size_width}}  {used:>{used_width}}  "
        f"{percent:>{percent_width}}  {free:>{free_width}}  {status}"
        for name, size, used, percent, free, status in volumes
    ]
    return f"<b>Disk space</b>\n\n{header}", rows or ["No disks found"]


def cpu_times():
    samples = {}
    with open("/proc/stat", encoding="ascii") as stats:
        for line in stats:
            name, *fields = line.split()
            if not name.startswith("cpu"):
                break
            times = [int(field) for field in fields[:8]]
            samples[name] = (sum(times), times[3] + times[4])
    return samples


def cpu_sampler():
    previous = {}

    def sample():
        nonlocal previous
        current = cpu_times()
        rows = []
        for name, (total, idle) in current.items():
            label = "Total" if name == "cpu" else f"CPU {name[3:]}"
            usage = "—"
            filled = 0
            if name in previous:
                previous_total, previous_idle = previous[name]
                elapsed = total - previous_total
                if elapsed > 0:
                    busy = elapsed - (idle - previous_idle)
                    percent = 100 * max(0, min(busy, elapsed)) / elapsed
                    usage = f"{percent:.1f}%"
                    filled = round(percent / 5)
            meter = "█" * filled + "░" * (20 - filled)
            rows.append(f"{label:<8} {usage:>6}  {meter}")
        previous = current
        return rows

    return sample


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stat", choices=("disk", "cpu"))
    stat = parser.parse_args().stat
    display = Gdk.Display.get_default()
    pointer = display.get_default_seat().get_pointer()
    _, click_x, click_y = pointer.get_position()
    monitor = display.get_monitor_at_point(click_x, click_y).get_geometry()
    refresh_rows = None
    try:
        if stat == "cpu":
            refresh_rows = cpu_sampler()
            heading, rows = "<b>CPU usage</b>", refresh_rows()
        else:
            heading, rows = disk_overview()
    except (OSError, ValueError, subprocess.SubprocessError):
        heading = f"<b>{stat.upper() if stat == 'cpu' else 'Disk'}</b>"
        rows = ["Usage data is unavailable"]
    show_popup(heading, rows, pointer, monitor, click_x, refresh_rows)


if __name__ == "__main__":
    main()
