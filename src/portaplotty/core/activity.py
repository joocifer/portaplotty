from __future__ import annotations

import subprocess
import time
from collections import deque

# At a 3s sample cadence, 40 samples ≈ 2 minutes of history per port.
MAX_SAMPLES = 40


def _parse_established(output: str) -> dict[tuple[int, int], int]:
    """Parse `lsof -nP -iTCP -sTCP:ESTABLISHED -F pn` into {(pid, local_port): count}.

    Records are field-tagged; an `n` line looks like
    "127.0.0.1:7878->127.0.0.1:54321" — the local end is left of "->".
    """
    counts: dict[tuple[int, int], int] = {}
    pid: int | None = None
    for line in output.splitlines():
        if not line:
            continue
        tag, val = line[0], line[1:]
        if tag == "p":
            pid = int(val) if val.isdigit() else None
        elif tag == "n" and pid is not None:
            local = val.split("->", 1)[0]
            _, _, port_s = local.rpartition(":")
            if port_s.isdigit():
                key = (pid, int(port_s))
                counts[key] = counts.get(key, 0) + 1
    return counts


def _sample_established() -> dict[tuple[int, int], int]:
    proc = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:ESTABLISHED", "-F", "pn"],
        capture_output=True,
        text=True,
        check=False,
    )
    return _parse_established(proc.stdout)


class ActivityMonitor:
    """Holds a per-(pid, port) ring buffer of ESTABLISHED-connection counts.

    `sample()` is called on a background cadence; `snapshot()` is read by the
    API. Keys that have gone fully idle (a complete buffer of zeros) are pruned
    so dead processes don't accumulate forever.
    """

    def __init__(self, max_samples: int = MAX_SAMPLES):
        self.max_samples = max_samples
        self.history: dict[tuple[int, int], deque[dict]] = {}

    def sample(self) -> None:
        counts = _sample_established()
        t = round(time.time(), 1)
        for key in set(self.history) | set(counts):
            buf = self.history.get(key)
            if buf is None:
                buf = deque(maxlen=self.max_samples)
                self.history[key] = buf
            buf.append({"t": t, "established": counts.get(key, 0)})
            if len(buf) == self.max_samples and not any(s["established"] for s in buf):
                del self.history[key]

    def snapshot(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for (pid, port), buf in self.history.items():
            samples = list(buf)
            out[f"{pid}:{port}"] = {
                "samples": samples,
                "current": samples[-1]["established"] if samples else 0,
                "peak": max((s["established"] for s in samples), default=0),
            }
        return out
