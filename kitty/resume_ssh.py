"""Start a persistent Screen session for an interactive Kitty login to lap."""

import getopt
import os
import re
from uuid import uuid4


SESSION_NAME = re.compile(r"resume-[0-9a-f]{32}")
SSH_OPTIONS = "46AaCfGgKkMNnqsTtVvXxYyZB:b:c:D:E:e:F:I:i:J:L:l:m:O:o:P:p:Q:R:S:W:w:"
SSH_LAP = ("ssh", "-t", "lap")
SCREEN4 = "screen"
SCREEN5 = "~/.local/bin/screen5"
ATTACH = ("-d", "-R", "-S")


def ssh_args(session, screen=SCREEN5):
    if SESSION_NAME.fullmatch(session) is None:
        raise ValueError("Invalid Screen session name")
    return [*SSH_LAP, screen, "-q", *ATTACH, session]


def screen_session(argv):
    if not argv or SESSION_NAME.fullmatch(argv[-1]) is None:
        return None
    prefix = (os.path.basename(argv[0]), *argv[1:-1])
    for screen in (SCREEN4, SCREEN5):
        command = (*SSH_LAP, screen)
        if prefix in ((*command, *ATTACH), (*command, "-q", *ATTACH)):
            return argv[-1], screen
    return None


def quiet_saved_session(session):
    """Upgrade launch commands written before quiet mode was enabled."""
    legacy_suffix = " " + " ".join((*SSH_LAP, SCREEN4, *ATTACH)) + " "
    lines = []
    for line in session.strip().splitlines():
        if line.startswith("launch "):
            launch, separator, name = line.rpartition(legacy_suffix)
            if separator and SESSION_NAME.fullmatch(name):
                line = f"{launch} {' '.join(ssh_args(name, SCREEN4))}"
        lines.append(line)
    return "\n".join(lines)


def is_interactive_lap_ssh(argv):
    if not argv or os.path.basename(argv[0]) != "ssh":
        return False
    try:
        options, arguments = getopt.getopt(argv[1:], SSH_OPTIONS)
        if not arguments or arguments[0].rsplit("@", 1)[-1] != "lap":
            return False
        more_options, command = getopt.getopt(arguments[1:], SSH_OPTIONS)
    except getopt.GetoptError:
        return False
    flags = {flag for flag, _ in options + more_options}
    if flags & {"-f", "-G", "-N", "-O", "-Q", "-s", "-T", "-V", "-W"}:
        return False
    return not command or "-t" in flags


if __name__ == "__main__":
    args = ssh_args("resume-" + uuid4().hex)
    os.execvp(args[0], args)
