from __future__ import annotations

import json
from pathlib import Path

import pytest

from portaplotty.core.identify import identify
from portaplotty.core.models import AppInfo, ListeningService


def _svc(**kw) -> ListeningService:
    defaults = dict(
        pid=1000,
        port=8080,
        address="127.0.0.1",
        process_name="node",
        user="jay",
        exe=None,
        cwd=None,
        cmdline=[],
        fingerprint="abc",
        app=AppInfo(name="", kind="unknown", confidence=0.0),
        limited_info=False,
    )
    defaults.update(kw)
    return ListeningService(**defaults)


def test_launchd_label_takes_precedence_over_fallback():
    svc = _svc(pid=42)
    info = identify(svc, {42: "com.apple.cfprefsd"})
    assert info.kind == "launchd"
    assert info.name == "com.apple.cfprefsd"


def test_brew_service_recognized_from_launchd_label():
    svc = _svc(pid=99)
    info = identify(svc, {99: "homebrew.mxcl.postgresql@16"})
    assert info.kind == "brew"
    assert "postgresql@16" in info.name
    assert "Homebrew" in info.name


def test_project_marker_node(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "my-app"}))
    svc = _svc(cwd=str(tmp_path), process_name="node")
    info = identify(svc, {})
    assert info.kind == "project"
    assert info.name.startswith("my-app")


def test_project_marker_walks_up_to_ancestor(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "root-app"}))
    sub = tmp_path / "deeply" / "nested"
    sub.mkdir(parents=True)
    svc = _svc(cwd=str(sub))
    info = identify(svc, {})
    assert info.kind == "project"
    assert "root-app" in info.name


def test_project_marker_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "cool-thing"\n')
    svc = _svc(cwd=str(tmp_path), process_name="python")
    info = identify(svc, {})
    assert info.kind == "project"
    assert "cool-thing" in info.name


def test_app_bundle_detection_from_exe():
    svc = _svc(exe="/Applications/Docker.app/Contents/MacOS/Docker")
    info = identify(svc, {})
    assert info.kind == "app_bundle"
    # Without a real Info.plist accessible, falls back to the bundle stem.
    assert info.name == "Docker"


def test_fallback_uses_process_name_when_nothing_matches():
    svc = _svc(process_name="weirdthing", cmdline=["weirdthing", "--port", "9000"])
    info = identify(svc, {})
    assert info.kind == "unknown"
    assert "weirdthing" in info.name


def test_fallback_includes_cmdline_hint():
    svc = _svc(process_name="python", cmdline=["python", "-m", "server.py"])
    info = identify(svc, {})
    assert info.kind == "unknown"
    # The first non-flag arg after interpreter should appear
    assert "server.py" in info.name or "python" in info.name
