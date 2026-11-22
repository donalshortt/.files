import json
import subprocess
import sys


def entry_edge(rectangle, direction):
    if direction == "east":
        return rectangle["x"]
    if direction == "west":
        return -(rectangle["x"] + rectangle["width"])
    if direction == "south":
        return rectangle["y"]
    return -(rectangle["y"] + rectangle["height"])


def visible_windows(node):
    if node is None:
        return
    if node["client"] is not None and not node["hidden"]:
        yield node
    yield from visible_windows(node["firstChild"])
    yield from visible_windows(node["secondChild"])


def entry_window(desktop, direction):
    def rank(node):
        client = node["client"]
        state = client["state"]
        rectangle = client["floatingRectangle"] if state == "floating" else client["tiledRectangle"]
        focused = node["id"] == desktop["focusedNodeId"]
        return (not (focused and state == "fullscreen"), entry_edge(rectangle, direction), not focused)

    return min(visible_windows(desktop["root"]), key=rank, default=None)


def opposite_monitor(state, direction):
    if direction in ("west", "east"):
        cross_axis, cross_size = "y", "height"
    else:
        cross_axis, cross_size = "x", "width"

    monitors = state["monitors"]
    focused_id = state["focusedMonitorId"]
    focused = next(monitor["rectangle"] for monitor in monitors if monitor["id"] == focused_id)
    cross_start = focused[cross_axis]
    cross_end = cross_start + focused[cross_size]
    best_edge = entry_edge(focused, direction)
    target = None

    for monitor in monitors:
        rectangle = monitor["rectangle"]
        start = rectangle[cross_axis]
        end = start + rectangle[cross_size]
        if start >= cross_end or end <= cross_start:
            continue
        edge = entry_edge(rectangle, direction)
        if edge < best_edge:
            best_edge = edge
            target = monitor["id"]

    return target


def main():
    direction = sys.argv[1]
    result = subprocess.run(
        ["bspc", "query", "-T", "-d", f"{direction}.occupied:focused"],
        stdout=subprocess.PIPE,
    )
    if result.returncode == 0:
        desktop = json.loads(result.stdout)
        window = entry_window(desktop, direction)
        if window is not None:
            selector = f"{window['id']}.!hidden.window"
            if subprocess.call(["bspc", "node", "-f", selector]) == 0:
                return 0
        if subprocess.call(["bspc", "desktop", "-f", f"{desktop['id']}.active"]) == 0:
            return 0

    if subprocess.call(["bspc", "monitor", "-f", direction]) == 0:
        return 0

    state = json.loads(subprocess.check_output(["bspc", "wm", "-d"]))
    target = opposite_monitor(state, direction)
    if target is not None:
        return subprocess.call(["bspc", "monitor", "-f", str(target)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
