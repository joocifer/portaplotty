from __future__ import annotations

from portaplotty.core import activity
from portaplotty.core.activity import ActivityMonitor, _parse_established

_LSOF = """\
p1596
n127.0.0.1:3000->127.0.0.1:54321
p1596
n127.0.0.1:3000->127.0.0.1:54322
p1449
n[::1]:5432->[::1]:60001
p1449
n127.0.0.1:5432->127.0.0.1:60002
"""


def test_parse_counts_by_pid_and_local_port():
    counts = _parse_established(_LSOF)
    assert counts[(1596, 3000)] == 2
    # postgres: two established on port 5432 (ipv6 + ipv4), same pid → aggregated
    assert counts[(1449, 5432)] == 2


def test_parse_empty():
    assert _parse_established("") == {}


def test_parse_ignores_malformed_name_lines():
    counts = _parse_established("p10\nnno-arrow-no-port\np10\nn1.2.3.4:80->5.6.7.8:9\n")
    assert counts == {(10, 80): 1}


def test_monitor_records_and_snapshots(monkeypatch):
    seq = iter([{(1, 3000): 1}, {(1, 3000): 3}, {(1, 3000): 2}])
    monkeypatch.setattr(activity, "_sample_established", lambda: next(seq))
    m = ActivityMonitor()
    m.sample()
    m.sample()
    m.sample()
    snap = m.snapshot()
    assert snap["1:3000"]["current"] == 2
    assert snap["1:3000"]["peak"] == 3
    assert len(snap["1:3000"]["samples"]) == 3


def test_monitor_records_zero_when_port_goes_idle(monkeypatch):
    seq = iter([{(1, 3000): 2}, {}])  # second sample: no established
    monkeypatch.setattr(activity, "_sample_established", lambda: next(seq))
    m = ActivityMonitor()
    m.sample()
    m.sample()
    snap = m.snapshot()
    assert snap["1:3000"]["current"] == 0
    assert snap["1:3000"]["peak"] == 2


def test_monitor_prunes_fully_idle_keys(monkeypatch):
    monkeypatch.setattr(activity, "_sample_established", lambda: {})
    m = ActivityMonitor(max_samples=3)
    for _ in range(3):
        m.sample()
    # buffer filled with zeros → pruned
    assert m.snapshot() == {}
