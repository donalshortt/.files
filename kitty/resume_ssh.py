"""Start a persistent Screen session for an interactive Kitty login to lap."""

import getopt
import os
import re
import shlex
from uuid import uuid4


SESSION_NAME = re.compile(r"resume-[0-9a-f]{32}")
CODEX_THREAD_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE)
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
CODEX_START = "codex resume "
LOGIN_SHELL = '; exec "${SHELL:-/bin/sh}" -l'


def usable_cwd(cwd):
    return cwd.startswith("/") and "\0" not in cwd and cwd.splitlines() == [cwd]


def ssh_args(session, screen=SCREEN5, cwd="", *, codex=None):
    if SESSION_NAME.fullmatch(session) is None:
        raise ValueError("Invalid Screen session name")
    command = [screen, "-q", *ATTACH, session]
    if codex is not None:
        if CODEX_THREAD_ID.fullmatch(codex) is None:
            raise ValueError("Invalid Codex conversation ID")
        command.extend(("/bin/sh", "-c", CODEX_START + codex + LOGIN_SHELL))
    # Leave Screen's optional ~/ prefix for the remote shell to expand.
    attach = f"exec {screen} {shlex.join(command[1:])}"
    if usable_cwd(cwd):
        return [*SSH_LAP, f"cd -- {shlex.quote(cwd)} || cd; {attach}"]
    if codex is not None:
        return [*SSH_LAP, attach]
    return [*SSH_LAP, *command]


def screen_session(argv):
    login = interactive_ssh(argv)
    if not login:
        return None
    host, options, command = login
    if host != "lap" or tuple(options) not in ((TTY_OPTION,), TT_OPTIONS):
        return None
    if len(command) == 1:
        attach = command[0]
        try:
            if attach.startswith("cd -- "):
                directory, separator, rest = attach[len("cd -- "):].rpartition(" || cd; exec ")
                words = shlex.split(directory) if separator else []
                if len(words) != 1 or not words[0].startswith("/") or shlex.quote(words[0]) != directory:
                    return None
                attach = "exec " + rest
            if not attach.startswith("exec "):
                return None
            command = shlex.split(attach[len("exec "):])
        except ValueError:
            return None
    if tuple(command[-3:-1]) == ("/bin/sh", "-c"):
        startup = command[-1]
        thread = startup.removeprefix(CODEX_START).removesuffix(LOGIN_SHELL)
        if CODEX_THREAD_ID.fullmatch(thread) and startup == CODEX_START + thread + LOGIN_SHELL:
            command = command[:-3]
    if not command or SESSION_NAME.fullmatch(command[-1]) is None:
        return None
    prefix = tuple(command[:-1])
    for screen in (SCREEN4, SCREEN5):
        if prefix in ((screen, *ATTACH), (screen, "-q", *ATTACH)):
            return command[-1], screen
    return None


def prepare_saved_session(session, checkpoints=None):
    """Update saved SSH launches for the Screen sessions being restored."""
    checkpoints = checkpoints or {}
    legacy_suffix = " " + " ".join((*SSH_LAP, SCREEN4, *ATTACH)) + " "
    lines = []
    for line in session.strip().splitlines():
        if line.startswith("launch "):
            launch, separator, name = line.rpartition(legacy_suffix)
            if separator and SESSION_NAME.fullmatch(name):
                line = f"{launch} {' '.join(ssh_args(name, SCREEN4))}"
            if checkpoints:
                argv = shlex.split(line)
                # The generated launch options always precede the SSH argv.
                start = next((index for index, word in enumerate(argv) if word == "ssh"), len(argv))
                managed = screen_session(argv[start:])
                if managed and managed[0] in checkpoints:
                    checkpoint = checkpoints[managed[0]]
                    args = ssh_args(*managed, cwd=checkpoint.get("cwd", ""), codex=checkpoint.get("codex"))
                    line = shlex.join(argv[:start] + args)
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
