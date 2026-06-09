# PLAN

Build phases for `portaplotty`. Each phase has a verifiable success criterion. Don't move to the next phase until the current one passes.

## Decisions (locked)

- **Language**: Python 3.11+
- **Discovery**: shell out to `lsof -iTCP -sTCP:LISTEN -nP -F pcnL` and parse the `-F` machine-readable output. We tried `psutil.net_connections('inet')` first but it requires root on macOS; per-process `Process.net_connections()` works unprivileged but only sees current-user processes. `lsof` works unprivileged and sees everything we have permission to see. No active port scanning.
- **Web**: FastAPI + uvicorn serving JSON API and static React bundle from one process
- **CLI lib**: `rich` for the table
- **FE**: Vite + React + TypeScript, vanilla (no router, no UI framework)
- **DB**: SQLite at `~/.portaplotty/cache.db` (stdlib `sqlite3`)
- **Privileges**: run unprivileged; mark rows with limited info when other-user processes hide their cwd/cmdline
- **Refresh**: client-side polling every 3 seconds
- **Bind**: web UI binds `127.0.0.1` by default

## Architecture

```
portaplotty/
├── pyproject.toml
├── README.md
├── PLAN.md
├── CLAUDE.md
├── src/portaplotty/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py        # @dataclass ListeningService, AppInfo, Evidence
│   │   ├── discover.py      # psutil → list[ListeningService]
│   │   ├── launchd.py       # `launchctl list` parsing
│   │   ├── brew.py          # `brew services list` parsing
│   │   ├── identify.py      # heuristic chain → AppInfo
│   │   └── memory.py        # SQLite read/write
│   ├── cli.py               # `portaplotty` entry — rich table
│   └── server.py            # FastAPI app, static mount, uvicorn launcher
├── web/
│   ├── package.json, vite.config.ts, tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── ServiceCard.tsx
│       ├── DetailDrawer.tsx
│       ├── api.ts
│       └── styles.css       # dark theme, CSS variables, responsive grid
└── tests/
    ├── test_identify.py
    └── test_memory.py
```

## Core data shapes

```python
@dataclass
class Evidence:
    source: str           # "app_bundle" | "launchd" | "brew" | "project_marker" | "memory" | "fallback"
    detail: str           # "/Applications/Docker.app/Info.plist" | "com.apple.cfprefsd" | ...

@dataclass
class AppInfo:
    name: str
    description: str | None
    kind: str             # "app_bundle" | "launchd" | "brew" | "project" | "remembered" | "unknown"
    confidence: float     # 0..1
    evidence: list[Evidence]
    previously_seen: bool

@dataclass
class ListeningService:
    pid: int
    port: int
    address: str          # "127.0.0.1" | "::" | "0.0.0.0"
    process_name: str     # psutil .name()
    exe: str | None
    cwd: str | None
    cmdline: list[str]
    user: str
    app: AppInfo
    fingerprint: str      # sha1(exe + cwd) — stable across PID rotation
    limited_info: bool    # True when other-user process hid cwd/cmdline
```

## Phase 1 — scaffold + discovery

**Deliverable**: `pyproject.toml`, package layout, `core/models.py`, `core/discover.py`.

`discover.list_listening()` shells out to `lsof -iTCP -sTCP:LISTEN -nP -F pcnL`, parses the field-tagged output, and enriches each row with `exe`/`cwd`/`cmdline` from `psutil.Process(pid)`. `psutil.AccessDenied` on per-process attributes sets `limited_info=True`. `app` is left as a placeholder for Phase 2.

**Verify**: `list_listening()` returns the same set of unique PIDs as `lsof -iTCP -sTCP:LISTEN -nP`. ✅ Verified — 22 PIDs each, zero diff.

## Phase 2 — launchd, brew, identification

**Deliverable**: `core/launchd.py`, `core/brew.py`, `core/identify.py`.

`launchd.pid_to_label()` returns `dict[int, str]` from `launchctl list`.
`brew.pid_to_formula()` returns `dict[int, str]` from `brew services list --json` (skipped if `brew` not installed).
`identify.identify(service)` runs the heuristic chain in order, returns `AppInfo`. Project markers checked: `package.json`, `pyproject.toml`, `setup.py`, `Cargo.toml`, `go.mod`, `Gemfile`, `mix.exs`, `composer.json`.

**Verify**: `tests/test_identify.py` covers each heuristic in isolation with mocked process data. All pass.

## Phase 3 — SQLite memory

**Deliverable**: `core/memory.py`, integration into `identify.py`.

Schema:

```sql
CREATE TABLE apps (
  fingerprint TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  kind TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
```

`memory.lookup(fingerprint) -> AppRecord | None` — read.
`memory.remember(fingerprint, name, description, kind)` — upsert; bumps `last_seen`.
`memory.touch(fingerprint)` — bump `last_seen` only.

Integration: after the heuristic chain runs, if `kind in ("unknown", "project", "remembered")`, check the cache. If found and the cached name differs from the fresh guess, prefer the cached one and set `previously_seen=True`. Either way, upsert/touch so `last_seen` reflects this run. High-confidence matches (`app_bundle`, `launchd`, `brew`) skip the cache entirely — those names are authoritative.

**Verify**: `tests/test_memory.py` — round-trip lookup/remember/touch against a tmp DB.

## Phase 4 — CLI

**Deliverable**: `cli.py`, console_script entry `portaplotty`.

```
portaplotty [--range 3000-9000] [--json] [--no-cache]
portaplotty serve [--host 127.0.0.1] [--port 7878]
```

Default table columns: App, Process, PID, Port, Info. Ports in 3000–9000 highlighted (cyan). Rows with `limited_info=True` get a dim style and a "limited info" tag in the Info column. Rows with `previously_seen=True` get a small `★` next to the name.

**Verify**: run `portaplotty` on the dev machine, eyeball the table — every listening port from `lsof` shows up, the highlight works, `--json` produces parseable JSON.

## Phase 5 — FastAPI server

**Deliverable**: `server.py`.

Endpoints:

- `GET  /api/services` → `[ListeningService]` as JSON (pydantic-serialized)
- `GET  /api/services/{pid}` → single service or 404
- `PATCH /api/apps/{fingerprint}` body `{name?, description?}` → updates memory; returns the updated record
- `GET  /` and `/assets/*` → static files from `web/dist`

`portaplotty serve` runs uvicorn on this app. CORS not enabled (same-origin only).

**Verify**: `curl http://127.0.0.1:7878/api/services | jq '. | length'` returns the same count as the CLI shows.

## Phase 6 — React web FE

**Deliverable**: `web/` Vite project, built into `web/dist`, served by FastAPI.

UI:

- Top bar: title, total count, "showing X / Y" filter status, range filter input
- Grid of cards (CSS grid, `minmax(260px, 1fr)`)
- Card: port (large), app name, process name + PID (small), kind badge, ★ if previously seen
- Click → right-side drawer with: address, user, cwd, full cmdline, evidence list, edit form for name + description (PATCH the API), close button
- Dark theme: near-black background, single accent color, no shadows except the drawer
- Poll `/api/services` every 3s; diff to avoid re-rendering unchanged cards

**Verify**: `npm run build`, then `portaplotty serve`, open the URL — see services, click one, rename it, refresh the CLI, see the new name persist.

## Quality gates

- `ruff` + `ruff format` clean
- `pytest` green
- TypeScript `tsc --noEmit` clean for the FE

## Out of scope (do not build)

UDP, remote hosts, sightings history beyond `last_seen`, web UI auth, packaging as a `.app`, menubar app, notifications. All deferrable.
