#!/usr/bin/env python3
import argparse
import ctypes
import json
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from pathlib import Path

import gi

from lap_usage import parse_meminfo, read_lap

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


@contextmanager
def background_rows(read_rows):
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = None

        def poll():
            nonlocal pending
            if pending is not None and not pending.done():
                return None
            finished = pending
            pending = executor.submit(read_rows)
            return finished.result() if finished is not None else None

        yield poll


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
            updated = refresh_rows()
            if updated is not None:
                body.set_text("\n".join(updated))
        except (OSError, ValueError, subprocess.SubprocessError):
            body.set_text("Usage data is unavailable")
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


def disk_overview(lap=False):
    command = ["lsblk", "--bytes", "--json", "--list", "--exclude", "7", "--output",
               "NAME,TYPE,SIZE,FSSIZE,FSUSED,FSAVAIL,MOUNTPOINT"]
    if lap:
        output = read_lap(f"exec {shlex.join(command)}\n")
    else:
        output = subprocess.run(command, capture_output=True, text=True, check=True, timeout=5).stdout

    volumes = [("Device", "Size", "Used", "Used %", "Free", "Mount / status")]
    for device in json.loads(output)["blockdevices"]:
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
    return header, rows or ["No disks found"]


def memory_overview(lap=False):
    if lap:
        contents = read_lap("exec cat /proc/meminfo\n")
    else:
        contents = Path("/proc/meminfo").read_text(encoding="ascii")

    memory_kib = parse_meminfo(contents)
    rows = [f"{'':<5}  {'Used':>10}  {'Available':>10}  {'Total':>10}"]
    for label, total, available in [
        ("RAM", memory_kib["MemTotal"], memory_kib["MemAvailable"]),
        ("Swap", memory_kib["SwapTotal"], memory_kib["SwapFree"]),
    ]:
        used_gib = (total - available) / 1024**2
        available_gib = available / 1024**2
        total_gib = total / 1024**2
        rows.append(f"{label:<5}  {used_gib:>6.2f} GiB  {available_gib:>6.2f} GiB  {total_gib:>6.2f} GiB")
    return rows


def cpu_times(lap=False):
    if lap:
        stats = read_lap("exec grep '^cpu' /proc/stat\n")
    else:
        stats = Path("/proc/stat").read_text(encoding="ascii")

    samples = {}
    for line in stats.splitlines():
        if not line.startswith("cpu"):
            break
        name, *fields = line.split()
        if len(fields) < 8:
            raise ValueError("Missing CPU counters")
        times = [int(field) for field in fields[:8]]
        samples[name] = (sum(times), times[3] + times[4])
    if "cpu" not in samples:
        raise ValueError("Missing aggregate CPU counters")
    return samples


def cpu_sampler(lap=False):
    previous = {}

    def sample():
        nonlocal previous
        current = cpu_times(lap)
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
    parser.add_argument("stat", choices=("disk", "cpu", "memory"))
    parser.add_argument("--lap", action="store_true", help="Show details from lap")
    args = parser.parse_args()

    display = Gdk.Display.get_default()
    pointer = display.get_default_seat().get_pointer()
    _, click_x, click_y = pointer.get_position()
    monitor = display.get_monitor_at_point(click_x, click_y).get_geometry()
    title = {"cpu": "CPU usage", "disk": "Disk space", "memory": "RAM usage"}[args.stat]
    heading = f"<b>{'lap · ' if args.lap else ''}{title}</b>"
    refresh_rows = None
    try:
        if args.stat == "cpu":
            sample = cpu_sampler(args.lap)
            rows = sample()
            refresh_rows = sample
        elif args.stat == "disk":
            header, rows = disk_overview(args.lap)
            heading += f"\n\n{header}"
        else:
            rows = memory_overview(args.lap)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        rows = ["Usage data is unavailable"]
    refresh = background_rows(refresh_rows) if args.lap and refresh_rows else nullcontext(refresh_rows)
    with refresh as poll_rows:
        show_popup(heading, rows, pointer, monitor, click_x, poll_rows)


if __name__ == "__main__":
    main()
