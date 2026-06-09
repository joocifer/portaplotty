from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass

import psutil

from .models import AppInfo, ListeningService


@dataclass
class _RawListener:
    pid: int
    command: str
    user: str
    address: str
    port: int


def _fingerprint(exe: str | None, cwd: str | None, command: str, pid: int) -> str:
    """Stable identity across PID rotation.

    Prefer (exe, cwd) since those persist across restarts of the same app.
    If both are unknown (other-user process), fall back to (command, pid) —
    not stable, but at least unique within this snapshot.
    """
    if exe or cwd:
        raw = f"{exe or ''}|{cwd or ''}".encode()
    else:
        raw = f"unknown|{command}|{pid}".encode()
    return hashlib.sha1(raw).hexdigest()


def _parse_lsof(output: str) -> list[_RawListener]:
    """Parse `lsof -F pcnL` output. Each record starts with `p<pid>`.

    Field prefixes:
      p = pid, c = command, L = login (user), f = fd, n = name (addr:port)
    """
    listeners: list[_RawListener] = []
    pid: int | None = None
    command = ""
    user = ""
    for line in output.splitlines():
        if not line:
            continue
        tag, value = line[0], line[1:]
        if tag == "p":
            pid = int(value)
            command = ""
            user = ""
        elif tag == "c":
            command = value
        elif tag == "L":
            user = value
        elif tag == "n" and pid is not None:
            # value looks like "*:5000" or "127.0.0.1:8080" or "[::1]:7878"
            if ":" not in value:
                continue
            addr, _, port_s = value.rpartition(":")
            try:
                port = int(port_s)
            except ValueError:
                continue
            if addr.startswith("[") and addr.endswith("]"):
                addr = addr[1:-1]
            if addr == "*":
                addr = "0.0.0.0"
            listeners.append(_RawListener(pid, command, user, addr, port))
    return listeners


def _enrich(raw: _RawListener) -> ListeningService:
    exe: str | None = None
    cwd: str | None = None
    cmdline: list[str] = []
    limited_info = False
    try:
        p = psutil.Process(raw.pid)
        with p.oneshot():
            try:
                exe = p.exe() or None
            except (psutil.AccessDenied, psutil.ZombieProcess):
                limited_info = True
            try:
                cwd = p.cwd() or None
            except (psutil.AccessDenied, psutil.ZombieProcess):
                limited_info = True
            try:
                cmdline = p.cmdline()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                limited_info = True
    except psutil.NoSuchProcess:
        limited_info = True

    fp = _fingerprint(exe, cwd, raw.command, raw.pid)
    return ListeningService(
        pid=raw.pid,
        port=raw.port,
        address=raw.address,
        process_name=raw.command,
        user=raw.user,
        exe=exe,
        cwd=cwd,
        cmdline=cmdline,
        fingerprint=fp,
        app=AppInfo(name=raw.command or f"pid-{raw.pid}", kind="unknown", confidence=0.0),
        limited_info=limited_info,
    )


def list_listening() -> list[ListeningService]:
    if shutil.which("lsof") is None:
        raise RuntimeError("lsof not found in PATH; portaplotty requires lsof on macOS")
    proc = subprocess.run(
        ["lsof", "-iTCP", "-sTCP:LISTEN", "-nP", "-F", "pcnL"],
        capture_output=True,
        text=True,
        check=False,
    )
    raws = _parse_lsof(proc.stdout)
    seen: set[tuple[int, int, str]] = set()
    services: list[ListeningService] = []
    for raw in raws:
        key = (raw.pid, raw.port, raw.address)
        if key in seen:
            continue
        seen.add(key)
        services.append(_enrich(raw))
    services.sort(key=lambda s: (s.port, s.pid))
    return services
