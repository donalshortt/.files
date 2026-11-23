#!/usr/bin/python3
"""Read lap's root disk, memory, and CPU usage for Polybar."""

import subprocess


POPUP = '/usr/bin/python3 -B "$HOME/.files/polybar/scripts/system-overview.py"'
SAMPLE = """
set -e
export LC_ALL=C
head -n 1 /proc/stat
sleep 0.5
head -n 1 /proc/stat
grep -E '^Mem(Total|Available):' /proc/meminfo
stat -f -c '%b %f %a' /
"""


def read_lap(command):
    return subprocess.run(
        ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2",
         "-o", "StrictHostKeyChecking=yes", "-o", "ClearAllForwardings=yes",
         "-o", "ForwardAgent=no", "-o", "ForwardX11=no", "-o", "PermitLocalCommand=no",
         "-o", "RemoteCommand=none", "--", "lap", "sh", "-s"],
        input=command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, check=True, timeout=4,
    ).stdout


def parse_meminfo(contents):
    memory_kib = {}
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == "kB":
            memory_kib[fields[0].removesuffix(":")] = int(fields[1])
    return memory_kib


def cpu_times(line):
    name, *fields = line.split()
    if name != "cpu" or len(fields) < 8:
        raise ValueError("Missing aggregate CPU counters")
    # Guest time is already included in user and nice time.
    ticks = list(map(int, fields[:8]))
    return sum(ticks), ticks[3] + ticks[4]


def format_usage(sample):
    first, second, *memory, disk = sample.splitlines()
    before, idle_before = cpu_times(first)
    after, idle_after = cpu_times(second)
    elapsed = after - before

    memory_kib = parse_meminfo("\n".join(memory))
    ram_gib = (memory_kib["MemTotal"] - memory_kib["MemAvailable"]) / 1024**2

    blocks, free, available = map(int, disk.split())
    used = blocks - free
    if elapsed <= 0 or used + available <= 0:
        raise ValueError("Usage could not be calculated")
    disk_percent = 100 * used / (used + available)
    busy = elapsed - (idle_after - idle_before)
    cpu_percent = 100 * max(0, min(busy, elapsed)) / elapsed

    return (
        f"lap  %{{A1:{POPUP} disk --lap:}}%{{T1}}%{{T2}} {disk_percent:.0f}%%{{A}}"
        f"  %{{A1:{POPUP} memory --lap:}}%{{T1}}%{{T2}} {ram_gib:.2f} GiB%{{A}}"
        f"  %{{A1:{POPUP} cpu --lap:}}%{{T1}}%{{T2}} {cpu_percent:.0f}%%{{A}}"
    )


def main():
    try:
        print(format_usage(read_lap(SAMPLE)))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print("lap: unavailable")


if __name__ == "__main__":
    main()
