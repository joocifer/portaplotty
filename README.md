# portaplotty

Find what's listening on ports on your Mac, and figure out which "app" each one belongs to.

`portaplotty` enumerates every TCP listener on your machine via `psutil` (the same data `lsof -iTCP -sTCP:LISTEN -nP` gives you), cross-references PIDs against `launchctl list` and `brew services list`, walks the working directory looking for project markers (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, ...), and presents the result either as an ASCII table in the terminal or as a dark-themed web UI.

It also remembers what it's seen. The first time an unrecognized dev server shows up on port 5173, you can give it a name ("vite — portaplotty FE"). Next time the same executable runs in the same directory, that name comes back.

## Install

Requires Python 3.11+.

```sh
pip install -e .
```

For the web UI, also build the FE bundle once:

```sh
cd web && npm install && npm run build
```

## Usage

CLI — ASCII table of every TCP listener:

```sh
portaplotty
```

```
┌──────────────────────┬─────────────┬───────┬───────┬─────────────────────────────┐
│ App                  │ Process     │ PID   │ Port  │ Info                        │
├──────────────────────┼─────────────┼───────┼───────┼─────────────────────────────┤
│ Docker Desktop       │ com.docker. │ 1842  │ 2375  │ .app bundle                 │
│ portaplotty (vite)   │ node        │ 84211 │ 5173  │ project: package.json       │
│ Postgres (Homebrew)  │ postgres    │  712  │ 5432  │ brew service                │
│ com.apple.cfprefsd   │ cfprefsd    │  281  │ 8770  │ launchd                     │
└──────────────────────┴─────────────┴───────┴───────┴─────────────────────────────┘
```

Web UI:

```sh
portaplotty serve
# → http://127.0.0.1:7878
```

Dark, responsive grid of cards — one per listening service. Click a card for cwd, full cmdline, launchd label, evidence trail, and (for unregistered apps) the ability to assign a name and description that sticks.

## Flags

- `--range 3000-9000` — only show ports in a range (default shows all, highlights the dev range)
- `--json` — emit JSON instead of the table
- `--no-cache` — ignore the SQLite memory of previously-named apps
- `serve --port 7878` — change the web UI port
- `serve --host 127.0.0.1` — bind address (defaults to loopback only)

## Permissions

`portaplotty` runs unprivileged. Some processes owned by other users (including root) won't expose their `cwd` or `cmdline` to your user — those rows still appear, but identification falls back to the executable name and the row is marked "limited info". Run with `sudo` if you want full detail on system services.

## How identification works

For each listening PID, in order, first match wins:

1. **`.app` bundle** — process path contains `*.app/Contents/MacOS/…` → bundle display name from `Info.plist`
2. **launchd-managed** — PID appears in `launchctl list` → use the reverse-DNS label
3. **Homebrew service** — PID appears in `brew services list` → use the formula name
4. **Project directory** — `cwd` (or an ancestor) contains a known project marker → use the project's name
5. **Remembered** — fingerprint (`sha1(exe_path + cwd)`) is in the SQLite cache → reuse the previously-assigned name
6. **Fallback** — executable basename plus a hint from the command line

Every row carries its confidence level and the evidence that produced the name, so you can see why something was labeled the way it was.

## Out of scope

- UDP listeners
- Remote Macs
- Persistent history of past sightings (only the most recent name/description per fingerprint is kept)
- Auth on the web UI (it binds to loopback)
