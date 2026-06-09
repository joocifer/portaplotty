from __future__ import annotations

from pathlib import Path

from portaplotty.core.identify import apply_memory
from portaplotty.core.memory import Memory
from portaplotty.core.models import AppInfo, ListeningService


def _svc(fp: str, kind: str, name: str) -> ListeningService:
    return ListeningService(
        pid=1, port=8000, address="127.0.0.1", process_name="x", user="u",
        exe=None, cwd=None, cmdline=[], fingerprint=fp,
        app=AppInfo(name=name, kind=kind, confidence=0.5),
    )


def test_remember_then_lookup_roundtrip(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    r = m.remember("fp1", "Some App", "project")
    assert r.first_seen == r.last_seen
    got = m.lookup("fp1")
    assert got is not None
    assert got.name == "Some App"
    assert got.kind == "project"


def test_lookup_missing_returns_none(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    assert m.lookup("never") is None


def test_touch_updates_last_seen_only(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    m.remember("fp", "n", "project")
    first = m.lookup("fp")
    assert first
    m.touch("fp")
    after = m.lookup("fp")
    assert after
    assert after.first_seen == first.first_seen


def test_update_user_fields(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    m.remember("fp", "Old Name", "project")
    updated = m.update_user_fields("fp", name="New Name", description="My dev server")
    assert updated
    assert updated.name == "New Name"
    assert updated.description == "My dev server"


def test_update_user_fields_unknown_returns_none(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    assert m.update_user_fields("nope", name="x") is None


def test_apply_memory_remembers_unknown(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    svc = _svc("fp1", "unknown", "node: server.js")
    apply_memory(svc, m)
    assert svc.app.previously_seen is False  # first time
    rec = m.lookup("fp1")
    assert rec and rec.name == "node: server.js"


def test_apply_memory_reuses_user_renamed_name(tmp_path: Path):
    m = Memory(tmp_path / "c.db")
    m.remember("fp1", "My Custom Name", "unknown", description="My dev server")
    svc = _svc("fp1", "unknown", "node: server.js")
    apply_memory(svc, m)
    assert svc.app.previously_seen is True
    assert svc.app.name == "My Custom Name"
    assert svc.app.description == "My dev server"


def test_apply_memory_authoritative_kind_keeps_fresh_name(tmp_path: Path):
    """A .app bundle name should not be overridden by an old cached name."""
    m = Memory(tmp_path / "c.db")
    m.remember("fp1", "Old Cached Name", "app_bundle")
    svc = _svc("fp1", "app_bundle", "Docker")
    apply_memory(svc, m)
    assert svc.app.name == "Docker"  # fresh wins
    assert svc.app.previously_seen is True  # but we remember we've seen it
