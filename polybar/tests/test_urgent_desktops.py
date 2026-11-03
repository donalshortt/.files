"""Exercise Polybar's real bspwm renderer without creating an X window.

Run: python3 -B -m unittest discover -s polybar/tests
Requires a running X display for monitor queries and the polybar executable.
Polybar --stdout skips bar::start, so it creates no window or tray and only
reads the fake BSPWM_SOCKET used below; it never sends commands to real bspwm.
"""

import os
from pathlib import Path
import selectors
import socket
import subprocess
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]


def render(config, state, monitor_focused):
    monitor = subprocess.check_output(
        ["polybar", "--list-monitors"], text=True
    ).splitlines()[0].split(":", 1)[0]
    with tempfile.TemporaryDirectory(prefix="polybar-urgent-") as tmp:
        socket_path = str(Path(tmp) / "bspwm.sock")
        config_path = Path(tmp) / "probe.ini"
        config_path.write_text(
            f"include-file = {config}\n"
            "[bar/urgency-probe]\n"
            f"monitor = {monitor}\n"
            "width = 100%\nheight = 29\n"
            "background = ${colors.bg}\nforeground = ${colors.fg}\n"
            "font-0 = monospace:size=10\n"
            "modules-left = bspwm\nenable-ipc = false\n"
        )
        report = f"W{'M' if monitor_focused else 'm'}{monitor}:{state}9:LT:TT:G\n"
        server = socket.socket(socket.AF_UNIX)
        server.bind(socket_path)
        server.listen(1)
        server.settimeout(5)
        finished = threading.Event()
        errors = []

        def feed_report():
            try:
                with server.accept()[0] as connection:
                    request = connection.recv(4096)
                    if request != b"subscribe\0report\0":
                        raise AssertionError(f"Unexpected subscription: {request!r}")
                    connection.sendall(report.encode())
                    finished.wait(5)
            except Exception as error:
                errors.append(error)

        feeder = threading.Thread(target=feed_report, daemon=True)
        feeder.start()
        environment = dict(os.environ, BSPWM_SOCKET=socket_path)
        process = subprocess.Popen(
            ["polybar", "-s", "-l", "info", "-c", str(config_path), "urgency-probe"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = [], []
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, stdout)
        selector.register(process.stderr, selectors.EVENT_READ, stderr)
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                for key, _ in selector.select(0.05):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        key.data.append(chunk.decode())
                if "Parsing socket data:" in "".join(stderr) and stdout:
                    # The first stdout update may precede the fake report.
                    if "#bspwm.focus." in "".join(stdout):
                        break
                if process.poll() is not None:
                    break
            if errors:
                raise errors[0]
            output = "".join(stdout)
            if "#bspwm.focus." not in output:
                raise AssertionError(f"No desktop rendered: {output!r}\n{''.join(stderr)}")
            return output
        finally:
            process.terminate()
            process.communicate(timeout=5)
            finished.set()
            server.close()
            feeder.join(timeout=1)
            selector.close()


class UrgentDesktopTests(unittest.TestCase):
    def test_urgent_desktops_have_attention_marker(self):
        for config in sorted((ROOT / "polybar").glob("config*.ini")):
            for state, focused in (("u", False), ("U", False), ("U", True)):
                with self.subTest(config=config.name, state=state, monitor_focused=focused):
                    self.assertIn("!", render(config, state, focused))


if __name__ == "__main__":
    unittest.main()
