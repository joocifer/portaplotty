from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.discover import list_listening
from .core.identify import identify_all
from .core.memory import Memory

_WEB_DIST = Path(__file__).parent.parent.parent / "web" / "dist"


class AppPatch(BaseModel):
    name: str | None = None
    description: str | None = None


def _snapshot() -> list[dict]:
    services = list_listening()
    identify_all(services, memory=Memory())
    return [
        {**{k: v for k, v in asdict(s).items() if k != "app"}, "app": asdict(s.app)}
        for s in services
    ]


def create_app() -> FastAPI:
    app = FastAPI(title="portaplotty", docs_url=None, redoc_url=None)
    memory = Memory()

    @app.get("/api/services")
    def get_services():
        return _snapshot()

    @app.get("/api/services/{pid}")
    def get_service(pid: int):
        for svc in _snapshot():
            if svc["pid"] == pid:
                return svc
        raise HTTPException(status_code=404, detail=f"No listener with pid {pid}")

    @app.patch("/api/apps/{fingerprint}")
    def patch_app(fingerprint: str, patch: AppPatch):
        updated = memory.update_user_fields(
            fingerprint, name=patch.name, description=patch.description
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="No remembered app with that fingerprint")
        return asdict(updated)

    if _WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(_WEB_DIST / "index.html")
    else:
        @app.get("/")
        def index_missing():
            return JSONResponse(
                {
                    "error": "web bundle not built",
                    "hint": "cd web && npm install && npm run build",
                    "api": "/api/services",
                },
                status_code=503,
            )

    return app


def run(host: str = "127.0.0.1", port: int = 7878) -> None:
    uvicorn.run(create_app(), host=host, port=port, log_level="info")
