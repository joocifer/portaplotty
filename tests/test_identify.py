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


def test_bare_python_bundle_name_replaced_with_cwd():
    """A .app whose Info.plist resolves to just 'Python' should display the cwd instead."""
    svc = _svc(
        exe="/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
        cwd="/Users/jay/projects/my-script",
    )
    info = identify(svc, {})
    assert info.name == "/Users/jay/projects/my-script"
    # Evidence trail still shows the bundle was matched first
    sources = [e.source for e in info.evidence]
    assert "app_bundle" in sources
    assert "cwd_override" in sources


def test_bare_python_without_cwd_stays_as_python():
    """If there's no cwd to fall back to, the generic name remains."""
    svc = _svc(
        exe="/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
        cwd=None,
    )
    info = identify(svc, {})
    assert info.name == "Python"
