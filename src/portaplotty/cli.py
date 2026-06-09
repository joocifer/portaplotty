from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from .core.discover import list_listening
from .core.identify import identify_all
from .core.memory import Memory
from .core.models import ListeningService

_DEV_RANGE = range(3000, 9001)


def _parse_range(value: str) -> range:
    if "-" not in value:
        raise argparse.ArgumentTypeError("range must be LOW-HIGH, e.g. 3000-9000")
    low_s, high_s = value.split("-", 1)
    try:
        low, high = int(low_s), int(high_s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("range bounds must be integers") from e
    if low > high:
        raise argparse.ArgumentTypeError("range LOW must be <= HIGH")
    return range(low, high + 1)


def _gather(no_cache: bool, port_filter: range | None) -> list[ListeningService]:
    services = list_listening()
    if port_filter is not None:
        services = [s for s in services if s.port in port_filter]
    memory = None if no_cache else Memory()
    identify_all(services, memory=memory)
    return services


def _render_table(services: list[ListeningService], console: Console) -> None:
    table = Table(
        title=f"portaplotty — {len(services)} TCP listener(s)",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("App", style="cyan", no_wrap=False)
    table.add_column("Process", style="white")
    table.add_column("PID", justify="right", style="dim")
    table.add_column("Port", justify="right")
    table.add_column("Info", style="dim")

    for s in services:
        star = "★ " if s.app.previously_seen else ""
        name = f"{star}{s.app.name}"
        port_style = "bold cyan" if s.port in _DEV_RANGE else ""
        port_text = f"[{port_style}]{s.port}[/]" if port_style else str(s.port)
        info_bits = [s.app.kind]
        if s.address not in ("127.0.0.1", "::1"):
            info_bits.append(f"bind={s.address}")
        if s.limited_info:
            info_bits.append("limited info")
        if s.app.description:
            info_bits.append(s.app.description)
        row_style = "dim" if s.limited_info else ""
        table.add_row(
            name,
            s.process_name,
            str(s.pid),
            port_text,
            " · ".join(info_bits),
            style=row_style,
        )
    console.print(table)


def _emit_json(services: list[ListeningService]) -> None:
    payload = [
        {
            **{k: v for k, v in asdict(s).items() if k != "app"},
            "app": asdict(s.app),
        }
        for s in services
    ]
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _cmd_default(args: argparse.Namespace) -> int:
    services = _gather(args.no_cache, args.range)
    if args.json:
        _emit_json(services)
    else:
        _render_table(services, Console())
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import run

    run(host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="portaplotty",
        description="Find what's listening on ports on your Mac.",
    )
    parser.add_argument("--range", type=_parse_range, default=None,
                        help="Only show ports in LOW-HIGH (e.g. 3000-9000)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore the SQLite memory of previously-named apps")

    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="Run the web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7878)

    args = parser.parse_args(argv)

    if args.cmd == "serve":
        return _cmd_serve(args)
    return _cmd_default(args)


if __name__ == "__main__":
    raise SystemExit(main())
