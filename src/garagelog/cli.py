"""Command-line interface for garagelog.

Author: Marwan Helmy
"""

# TODO: add --json flag on more subcommands for scripting

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from garagelog.audit_log import AuditLog
from garagelog.backup import GarageBackup
from garagelog.errors import GaragelogError, NotFoundError, format_error
from garagelog.parser import parse_amount_ml, parse_date, parse_interval
from garagelog.vehicle import Vehicle, HealthStatus
from garagelog.reports import MonthlyReport
from garagelog.reminders import ReminderEngine
from garagelog.search import GarageSearch
from garagelog.server import run_server
from garagelog.stats import GarageStats
from garagelog.storage import JsonStorage
from garagelog.service import ServiceEvent
from garagelog import io_csv, io_jsonl, io_drivvo, io_carfax

__version__ = "1.2.0"
__author__ = "Marwan Helmy"


def _default_garage_path() -> Path:
    home = os.environ.get("GARAGELOG_HOME")
    if home:
        base = Path(home)
    else:
        base = Path.home() / ".garagelog"
    return base / "garage.json"


def _garage_path(ns: argparse.Namespace) -> Path:
    if getattr(ns, "garage", None):
        return Path(ns.garage)
    return _default_garage_path()


def _load(ns: argparse.Namespace) -> JsonStorage:
    path = _garage_path(ns)
    return JsonStorage(path)


def _resolve_vehicle(storage: JsonStorage, token: str) -> Vehicle:
    """Find vehicle by full id, id prefix, or case-insensitive name."""
    vehicles = storage.list_vehicles(active_only=False)
    if any(p.id == token for p in vehicles):
        return storage.get_vehicle(token)
    matches = [p for p in vehicles if p.id.startswith(token)]
    if len(matches) == 1:
        return matches[0]
    name_hits = [p for p in vehicles if p.name.lower() == token.lower()]
    if len(name_hits) == 1:
        return name_hits[0]
    nick_hits = [p for p in vehicles if p.nickname and p.nickname.lower() == token.lower()]
    if len(nick_hits) == 1:
        return nick_hits[0]
    partial = [p for p in vehicles if token.lower() in p.name.lower()]
    if len(partial) == 1:
        return partial[0]
    raise NotFoundError("vehicle", token)


def cmd_init(ns: argparse.Namespace) -> int:
    path = _garage_path(ns)
    path.parent.mkdir(parents=True, exist_ok=True)
    storage = JsonStorage(path)
    storage.save()
    print("Initialized garage at %s" % path)
    return 0


def cmd_add_vehicle(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    interval = parse_interval(ns.interval) if ns.interval else 7
    health = HealthStatus(ns.health) if ns.health else HealthStatus.UNKNOWN
    vehicle = Vehicle.create(
        ns.name,
        nickname=ns.nickname,
        make_key=ns.make,
        bay_id=ns.bay,
        health=health,
        service_interval_days=interval,
        acquired_at=ns.acquired,
        source="cli",
    )
    if ns.amount:
        vehicle.service_amount_ml = parse_amount_ml(ns.amount)
    created = storage.create_vehicle(vehicle)
    AuditLog(storage).record("create", "vehicle", created.id, details={"name": created.name})
    print("Added %s (%s)" % (created.display_name, created.id))
    return 0


def cmd_service(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    vehicle = _resolve_vehicle(storage, ns.vehicle)
    when = parse_date(ns.date).isoformat() if ns.date else date.today().isoformat()
    amount = parse_amount_ml(ns.amount) if ns.amount else vehicle.service_amount_ml
    if ns.skip:
        event = ServiceEvent.skip(vehicle.id, reason=ns.reason or "")
    else:
        event = ServiceEvent.create(
            vehicle_id=vehicle.id,
            serviced_at=when,
            amount_ml=amount,
            method=ns.method or "top_service",
            notes=ns.notes or "",
        )
    storage.create_service_event(event.to_dict())
    AuditLog(storage).record("service", "vehicle", vehicle.id, details={"event_id": event.id})
    if ns.skip:
        print("Skipped service for %s" % vehicle.display_name)
    else:
        print("Serviceed %s — %s" % (vehicle.display_name, event.summary()))
    return 0


def cmd_list(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    vehicles = storage.list_vehicles(active_only=not ns.all)
    if ns.overdue:
        vehicles = [p for p in vehicles if p.is_overdue()]
    if ns.bay:
        vehicles = [p for p in vehicles if p.bay_id == ns.bay]
    vehicles = sorted(vehicles, key=lambda p: p.name.lower())
    if not vehicles:
        print("No vehicles found.")
        return 0
    for p in vehicles[: ns.limit]:
        overdue = ""
        if p.is_overdue():
            overdue = " OVERDUE+%dd" % p.overdue_by_days()
        print(
            "{id} | {name} | {health} | every {iv}d{od}".format(
                id=p.id[:10],
                name=p.display_name[:40],
                health=p.health.value,
                iv=p.service_interval_days,
                od=overdue,
            )
        )
    if len(vehicles) > ns.limit:
        print("... and %d more (use --limit)" % (len(vehicles) - ns.limit))
    return 0


def cmd_report(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    today = date.today()
    year = ns.year or today.year
    month = ns.month or today.month
    report = MonthlyReport(storage)
    if ns.format == "json":
        import json
        print(json.dumps(report.generate(year, month), indent=2))
    else:
        print(report.render_text(year, month))
    return 0


def cmd_import(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    src = Path(ns.file)
    fmt = (ns.format or src.suffix.lstrip(".")).lower()
    result: int | dict | tuple = 0

    if fmt == "csv":
        kind = ns.kind or "vehicles"
        if kind == "vehicles":
            result = io_csv.import_vehicles_csv(storage, src, update=ns.update)
        elif kind == "service":
            result = io_csv.import_service_csv(storage, src)
        else:
            print("Unknown csv kind: %s" % kind, file=sys.stderr)
            return 1
    elif fmt == "jsonl":
        if ns.kind == "service":
            result = io_jsonl.import_service_jsonl(storage, src)
        elif ns.kind == "care":
            result = io_jsonl.import_care_jsonl(storage, src)
        else:
            result = io_jsonl.import_mixed_jsonl(storage, src)
    elif fmt == "drivvo":
        result = io_drivvo.import_drivvo(storage, src, update=ns.update)
    elif fmt == "carfax":
        result = io_carfax.import_carfax(storage, src, expand_quantity=not ns.no_expand)
    else:
        print("Unknown import format: %s" % fmt, file=sys.stderr)
        return 1

    AuditLog(storage).record("import", "garage", str(src), details={"format": fmt, "result": result})
    if isinstance(result, dict):
        print("Imported: %s" % ", ".join("%s=%d" % (k, v) for k, v in result.items() if k != "skipped"))
        if result.get("skipped"):
            print("  skipped %d unknown line(s)" % result["skipped"])
    else:
        print("Imported %d record(s)" % result)
    return 0


def cmd_export(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    dest = Path(ns.file)
    fmt = (ns.format or dest.suffix.lstrip(".")).lower()
    n: int | tuple = 0

    if fmt == "csv":
        kind = ns.kind or "vehicles"
        if kind == "vehicles":
            n = io_csv.export_vehicles_csv(storage, dest)
        elif kind == "service":
            n = io_csv.export_service_csv(storage, dest)
        elif kind == "bundle":
            n = io_csv.export_csv_bundle(storage, dest)
        else:
            print("Unknown csv kind: %s" % kind, file=sys.stderr)
            return 1
    elif fmt == "jsonl":
        if ns.kind == "service":
            n = io_jsonl.export_service_jsonl(storage, dest)
        elif ns.kind == "care":
            n = io_jsonl.export_care_jsonl(storage, dest)
        elif ns.kind == "full":
            n = io_jsonl.export_full_jsonl(storage, dest)
        else:
            n = io_jsonl.export_events_jsonl(storage, dest)
    else:
        print("Unknown export format: %s" % fmt, file=sys.stderr)
        return 1

    if isinstance(n, tuple):
        print("Exported vehicles=%d service=%d" % n)
    else:
        print("Exported %d record(s) -> %s" % (n, dest))
    return 0


def cmd_backup(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    garage_path = _garage_path(ns)
    backup_dir = Path(ns.dir) if ns.dir else garage_path.parent / "backups"
    gb = GarageBackup(garage_path, backup_dir)
    if ns.restore:
        safety = gb.restore(Path(ns.restore))
        print("Restored from %s (safety copy: %s)" % (ns.restore, safety))
        storage.load()
        return 0
    if ns.list:
        for p in gb.list_backups():
            print(p.name)
        return 0
    out = gb.create(label=ns.label)
    if ns.prune:
        removed = gb.prune(keep=ns.keep)
        print("Pruned %d old backup(s)" % len(removed))
    print("Backup -> %s" % out)
    return 0


def cmd_search(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    engine = GarageSearch(storage)
    query = ns.query or ""
    if not query:
        print("Provide a search query.", file=sys.stderr)
        return 1
    if ns.kind == "vehicles":
        hits = engine.search_vehicles(query)
    elif ns.kind == "care":
        hits = engine.search_inspection_logs(query)
    elif ns.kind == "notes":
        hits = engine.search_notes(query)
    else:
        hits = engine.search_all(query, limit=ns.limit)
    if not hits:
        print("No matches.")
        return 0
    for h in hits[: ns.limit]:
        print("[{kind}] {score:.0%} {title} ({id})".format(
            kind=h.kind,
            score=h.score,
            title=h.title[:50],
            id=h.id[:12],
        ))
        if h.snippet and ns.verbose:
            print("  %s" % h.snippet)
    print("%d result(s)" % len(hits))
    return 0


def cmd_reminders(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    engine = ReminderEngine(storage)
    if ns.overdue:
        items = engine.overdue_only()
    else:
        items = engine.upcoming(within_days=ns.within, include_overdue=True)
    if not items:
        print("All caught up.")
        return 0
    for r in items[: ns.limit]:
        if r.urgency == "overdue":
            flag = "!!"
        elif r.urgency == "due_today":
            flag = "->"
        else:
            flag = "  "
        print("{flag} {name} due {due} ({urg})".format(
            flag=flag,
            name=r.vehicle_name[:35],
            due=r.due_at.date(),
            urg=r.urgency,
        ))
    if len(items) > ns.limit:
        print("... %d more" % (len(items) - ns.limit))
    return 0


def cmd_stats(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    gs = GarageStats(storage)
    if ns.json:
        import json
        print(json.dumps(gs.snapshot(), indent=2))
    else:
        print(gs.render_text())
    return 0


def cmd_serve(ns: argparse.Namespace) -> int:
    path = str(_garage_path(ns))
    print("Serving %s on http://%s:%d/" % (path, ns.host, ns.port))
    run_server(path, host=ns.host, port=ns.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="garagelog",
        description="Personal housevehicle care tracker — Marwan Helmy",
    )
    p.add_argument(
        "--garage",
        help="Path to garage.json (default: ~/.garagelog/garage.json or GARAGELOG_HOME)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Create an empty garage.json")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("add-vehicle", help="Add a new vehicle")
    sp.add_argument("name")
    sp.add_argument("--nickname")
    sp.add_argument("--make", help="Make profile key")
    sp.add_argument("--bay", help="Bay id")
    sp.add_argument("--interval", default="7d", help="Service interval e.g. 7d, 2w")
    sp.add_argument("--amount", help="Default service amount e.g. 250ml")
    sp.add_argument("--acquired", help="Acquired date")
    sp.add_argument(
        "--health",
        choices=[h.value for h in HealthStatus],
        default="unknown",
    )
    sp.set_defaults(func=cmd_add_vehicle)

    sp = sub.add_parser("service", help="Log a service event")
    sp.add_argument("vehicle", help="Vehicle id or name")
    sp.add_argument("--amount", help="Service amount e.g. 250ml")
    sp.add_argument("--date", help="When (today, yesterday, YYYY-MM-DD)")
    sp.add_argument("--method", default="top_service")
    sp.add_argument("--notes", default="")
    sp.add_argument("--skip", action="store_true", help="Log a skipped service")
    sp.add_argument("--reason", default="", help="Skip reason")
    sp.set_defaults(func=cmd_service)

    sp = sub.add_parser("list", help="List vehicles")
    sp.add_argument("--all", action="store_true", help="Include archived")
    sp.add_argument("--overdue", action="store_true", help="Only overdue vehicles")
    sp.add_argument("--bay", help="Filter by bay id")
    sp.add_argument("--limit", type=int, default=100)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("report", help="Monthly care report")
    sp.add_argument("--year", type=int)
    sp.add_argument("--month", type=int)
    sp.add_argument("--format", choices=["text", "json"], default="text")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("import", help="Import from external format")
    sp.add_argument("file")
    sp.add_argument(
        "--format",
        choices=["csv", "jsonl", "drivvo", "carfax"],
        help="Auto-detected from extension if omitted",
    )
    sp.add_argument(
        "--kind",
        choices=["vehicles", "service", "care", "mixed"],
        default="vehicles",
        help="CSV/JSONL sub-type",
    )
    sp.add_argument("--update", action="store_true", help="Update existing vehicles on import")
    sp.add_argument(
        "--no-expand",
        action="store_true",
        help="Garage plan: one vehicle per row regardless of quantity",
    )
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("export", help="Export garage data")
    sp.add_argument("file")
    sp.add_argument("--format", choices=["csv", "jsonl"])
    sp.add_argument(
        "--kind",
        choices=["vehicles", "service", "care", "events", "full", "bundle"],
        default="vehicles",
    )
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("backup", help="Backup or restore garage.json")
    sp.add_argument("--dir", help="Backup directory")
    sp.add_argument("--label", help="Optional backup label")
    sp.add_argument("--list", action="store_true", help="List backups")
    sp.add_argument("--restore", metavar="FILE", help="Restore from backup file")
    sp.add_argument("--prune", action="store_true", help="Prune old backups after create")
    sp.add_argument("--keep", type=int, default=10, help="Backups to keep when pruning")
    sp.set_defaults(func=cmd_backup)

    sp = sub.add_parser("search", help="Search vehicles, care logs, notes")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--kind", choices=["all", "vehicles", "care", "notes"], default="all")
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("reminders", help="Upcoming and overdue service reminders")
    sp.add_argument("--within", type=int, default=14, help="Days ahead to show")
    sp.add_argument("--overdue", action="store_true", help="Overdue only")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_reminders)

    sp = sub.add_parser("stats", help="Garage statistics snapshot")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("serve", help="Start read-only HTTP dashboard")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    ns = parser.parse_args(argv)
    try:
        return ns.func(ns)
    except GaragelogError as exc:
        print("error: %s" % format_error(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
