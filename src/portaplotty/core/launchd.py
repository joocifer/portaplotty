from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def _has_launchctl() -> bool:
    return shutil.which("launchctl") is not None


def pid_to_label() -> dict[int, str]:
    """Map running PID → launchd label, via `launchctl list`.

    Output format (tab-separated):
        PID    Status  Label
        1322   0       com.apple.Finder
        -      -9      com.apple.cloudphotod    # not running, skipped
    """
    if not _has_launchctl():
        return {}
    proc = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True, check=False
    )
    result: dict[int, str] = {}
    for line in proc.stdout.splitlines()[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid_s, _status, label = parts[0], parts[1], parts[2]
        if pid_s == "-":
            continue
        try:
            result[int(pid_s)] = label
        except ValueError:
            continue
    return result
