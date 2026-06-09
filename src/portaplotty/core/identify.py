from __future__ import annotations

import os
import plistlib
import re
from pathlib import Path

from . import launchd
from .memory import Memory
from .models import AppInfo, Evidence, ListeningService

_PROJECT_MARKERS = {
    "package.json": ("name", "node"),
    "pyproject.toml": ("name", "python"),
    "setup.py": (None, "python"),
    "Cargo.toml": ("name", "rust"),
    "go.mod": ("module", "go"),
    "Gemfile": (None, "ruby"),
    "mix.exs": (None, "elixir"),
    "composer.json": ("name", "php"),
}

_APP_BUNDLE_RE = re.compile(r"(?P<bundle>/[^/]+(?:/[^/]+)*?/[^/]+\.app)(?=/|$)")


def _from_app_bundle(svc: ListeningService) -> AppInfo | None:
    if not svc.exe:
        return None
    match = _APP_BUNDLE_RE.search(svc.exe)
    if not match:
        return None
    bundle = match.group("bundle")
    name = Path(bundle).stem
    info_plist = Path(bundle) / "Contents" / "Info.plist"
    if info_plist.is_file():
        try:
            with info_plist.open("rb") as f:
                data = plistlib.load(f)
            name = (
                data.get("CFBundleDisplayName")
                or data.get("CFBundleName")
                or name
            )
        except (OSError, plistlib.InvalidFileException):
            pass
    return AppInfo(
        name=str(name),
        kind="app_bundle",
        confidence=0.95,
        evidence=[Evidence("app_bundle", bundle)],
    )


def _from_launchd(svc: ListeningService, labels: dict[int, str]) -> AppInfo | None:
    label = labels.get(svc.pid)
    if not label:
        return None
    if label.startswith("homebrew.mxcl."):
        formula = label[len("homebrew.mxcl.") :]
        return AppInfo(
            name=f"{formula} (Homebrew)",
            kind="brew",
            confidence=0.9,
            evidence=[Evidence("launchd", label)],
        )
    return AppInfo(
        name=label,
        kind="launchd",
        confidence=0.85,
        evidence=[Evidence("launchd", label)],
    )


def _read_project_name(path: Path, key: str | None) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if key is None:
        return path.parent.name
    if path.name == "package.json" or path.name == "composer.json":
        import json

        try:
            data = json.loads(text)
            return data.get(key) or path.parent.name
        except json.JSONDecodeError:
            return path.parent.name
    if path.name == "pyproject.toml":
        import tomllib

        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return path.parent.name
        return (
            data.get("project", {}).get("name")
            or data.get("tool", {}).get("poetry", {}).get("name")
            or path.parent.name
        )
    if path.name == "Cargo.toml":
        import tomllib

        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return path.parent.name
        return data.get("package", {}).get("name") or path.parent.name
    if path.name == "go.mod":
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("module "):
                return line[len("module ") :].strip().split("/")[-1]
        return path.parent.name
    return path.parent.name


def _from_project_marker(svc: ListeningService) -> AppInfo | None:
    if not svc.cwd:
        return None
    cwd = Path(svc.cwd)
    if not cwd.exists():
        return None
    for ancestor in [cwd, *cwd.parents]:
        for marker, (key, kind_hint) in _PROJECT_MARKERS.items():
            marker_path = ancestor / marker
            if marker_path.is_file():
                name = _read_project_name(marker_path, key) or ancestor.name
                hint = svc.process_name or kind_hint
                return AppInfo(
                    name=f"{name} ({hint})",
                    kind="project",
                    confidence=0.7,
                    evidence=[Evidence("project_marker", str(marker_path))],
                )
        # Stop walking up at the user's home dir to avoid matching unrelated parent projects.
        if ancestor == Path.home():
            break
    return None


def _fallback(svc: ListeningService) -> AppInfo:
    hint = ""
    if svc.cmdline and len(svc.cmdline) > 1:
        # Find the first non-flag arg that isn't the interpreter
        for arg in svc.cmdline[1:]:
            if not arg.startswith("-"):
                hint = os.path.basename(arg)
                break
    name = svc.process_name or f"pid-{svc.pid}"
    if hint:
        name = f"{name}: {hint}"
    return AppInfo(
        name=name,
        kind="unknown",
        confidence=0.3,
        evidence=[Evidence("fallback", svc.exe or svc.process_name)],
    )


def identify(svc: ListeningService, launchd_labels: dict[int, str]) -> AppInfo:
    """Run heuristic chain. First non-None wins. Always returns something."""
    for fn in (
        lambda s: _from_app_bundle(s),
        lambda s: _from_launchd(s, launchd_labels),
        lambda s: _from_project_marker(s),
    ):
        result = fn(svc)
        if result is not None:
            return result
    return _fallback(svc)


_AUTHORITATIVE_KINDS = {"app_bundle", "launchd", "brew"}


def apply_memory(svc: ListeningService, memory: Memory) -> None:
    """Cross-reference with SQLite memory. Mutates svc.app in place.

    For authoritative kinds (app_bundle/launchd/brew) the fresh name wins —
    we only touch last_seen so the cache reflects this run.

    For project/unknown kinds, a remembered name overrides the freshly
    guessed one (so user-assigned names stick), and previously_seen is set.
    Either way the cache is upserted.
    """
    record = memory.lookup(svc.fingerprint)
    if svc.app.kind in _AUTHORITATIVE_KINDS:
        memory.remember(
            svc.fingerprint,
            name=svc.app.name,
            kind=svc.app.kind,
            description=record.description if record else None,
        )
        if record:
            svc.app.previously_seen = True
            if record.description:
                svc.app.description = record.description
        return

    if record:
        svc.app.previously_seen = True
        # Prefer remembered name — user may have renamed it.
        svc.app.name = record.name
        svc.app.description = record.description
        svc.app.evidence.append(
            Evidence("memory", f"first_seen={record.first_seen}")
        )
        memory.touch(svc.fingerprint)
    else:
        memory.remember(
            svc.fingerprint,
            name=svc.app.name,
            kind=svc.app.kind,
        )


def identify_all(services: list[ListeningService], memory: Memory | None = None) -> None:
    """Mutates `services` in place, setting `.app` for each. If memory is None,
    skip the cache layer entirely (used for --no-cache)."""
    labels = launchd.pid_to_label()
    for svc in services:
        svc.app = identify(svc, labels)
        if memory is not None:
            apply_memory(svc, memory)
