from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Evidence:
    source: str
    detail: str


@dataclass
class AppInfo:
    name: str
    kind: str
    confidence: float
    description: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    previously_seen: bool = False


@dataclass
class ListeningService:
    pid: int
    port: int
    address: str
    process_name: str
    user: str
    exe: str | None
    cwd: str | None
    cmdline: list[str]
    fingerprint: str
    app: AppInfo
    limited_info: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
