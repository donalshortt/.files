"""Start a persistent Screen session for an interactive Kitty login to lap."""

import getopt
import os
import re
import shlex
from uuid import uuid4


SESSION_NAME = re.compile(r"resume-[0-9a-f]{32}")
SSH_DESTINATION = re.compile(r"[\w.][\w.:-]*(?:@[\w.][\w.:-]*)?", re.ASCII)
SSH_OPTIONS = "46AaCfGgKkMNnqsTtVvXxYyZB:b:c:D:E:e:F:I:i:J:L:l:m:O:o:P:p:Q:R:S:W:w:"
SSH_LAP = ("ssh", "-t", "lap")
TTY_OPTION = ("-t", "")
TT_OPTIONS = (
    TTY_OPTION,
    ("-o", "ClearAllForwardings=yes"),
    ("-o", "ControlMaster=no"),
    ("-o", "ControlPath=none"),
)
SCREEN4 = "screen"
SCREEN5 = "~/.local/bin/screen5"
ATTACH = ("-d", "-R", "-S")


def usable_cwd(cwd):
    return cwd.startswith("/") and "\0" not in cwd and cwd.splitlines() == [cwd]


def ssh_args(session, screen=SCREEN5, cwd=""):
    if SESSION_NAME.fullmatch(session) is None:
        raise ValueError("Invalid Screen session name")
    command = [screen, "-q", *ATTACH, session]
    if usable_cwd(cwd):
        return [*SSH_LAP, f'cd -- {shlex.quote(cwd)} || cd; exec {" ".join(command)}']
    return [*SSH_LAP, *command]


def screen_session(argv):
    login = interactive_ssh(argv)
    if not login:
        return None
    host, options, command = login
    if host != "lap" or tuple(options) not in ((TTY_OPTION,), TT_OPTIONS):
        return None
    if len(command) == 1 and command[0].startswith("cd -- "):
        directory, separator, attach = command[0][len("cd -- "):].rpartition(" || cd; exec ")
        try:
            words = shlex.split(directory) if separator else []
        except ValueError:
            return None
        if len(words) != 1 or not words[0].startswith("/") or shlex.quote(words[0]) != directory:
            return None
        command = attach.split()
    if not command or SESSION_NAME.fullmatch(command[-1]) is None:
        return None
    prefix = tuple(command[:-1])
    for screen in (SCREEN4, SCREEN5):
        if prefix in ((screen, *ATTACH), (screen, "-q", *ATTACH)):
            return command[-1], screen
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


def interactive_ssh(argv):
    if not argv or os.path.basename(argv[0]) != "ssh":
        return None
    try:
        options, arguments = getopt.getopt(argv[1:], SSH_OPTIONS)
        if not arguments or SSH_DESTINATION.fullmatch(arguments[0]) is None:
            return None
        more_options, command = getopt.getopt(arguments[1:], SSH_OPTIONS)
    except getopt.GetoptError:
        return None
    options += more_options
    flags = {flag for flag, _ in options}
    if flags & {"-f", "-G", "-N", "-O", "-Q", "-s", "-T", "-V", "-W"}:
        return None
    if command and "-t" not in flags:
        return None
    return arguments[0], options, command


def reconnect_login(login, remote_cwd=""):
    """Reopen a plain login without executing its previous remote command."""
    host, options, command = login
    if not command and all(flag in ("-t", "-q") for flag, _ in options):
        return ssh_args("resume-" + uuid4().hex, cwd=remote_cwd) if host == "lap" else ["ssh", "-t", host]

    # Kitty opens cloned remote panes with an explicit cd and login shell.
    # Drop the old connection's ControlPath and put the new login in Screen.
    clone_options = all(
        flag in ("-t", "-q")
        or (flag == "-o" and (value in ("ClearAllForwardings=yes", "ControlMaster=no")
                             or value.startswith("ControlPath=")))
        for flag, value in options
    )
    if host == "lap" and len(command) == 1 and clone_options:
        try:
            words = shlex.split(command[0])
        except ValueError:
            return []
        if (len(words) == 7 and words[:2] == ["cd", "--"] and usable_cwd(words[2])
                and words[3:] == ["&&", "exec", "${SHELL:-/bin/sh}", "-l"]):
            cwd = remote_cwd if usable_cwd(remote_cwd) else words[2]
            return ssh_args("resume-" + uuid4().hex, cwd=cwd)
    return []


if __name__ == "__main__":
    args = ssh_args("resume-" + uuid4().hex)
    os.execvp(args[0], args)
