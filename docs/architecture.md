# Architecture

*Marwan Helmy — how garagelog is put together*

I built garagelog as a single-user CLI first, then grew modules around it when I kept
needing "just one more thing" (seasonal intervals, Drivvo imports, issue notes). Nothing
here is microservices. It's one JSON file and a bunch of Python modules that know how
to read it.

## High-level picture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  cli.py     │────▶│ JsonStorage  │────▶│  garage.json    │
│  (commands) │     │  storage.py  │     │  (~/.garagelog) │
└─────────────┘     └──────┬───────┘     └─────────────────┘
       │                   │
       │            ┌──────┴───────┐
       ▼            ▼              ▼
  reports.py   vehicle.py       io_*.py (import/export)
  reminders.py service.py    backup.py / migrate.py
  schedule.py  inspection_log.py
```

The CLI is the main entry point (`garagelog` console script → `cli.py`). Everything
else is library code you can import in scripts — see `examples/` for that.

## Module map

| Module | Role |
|--------|------|
| `storage.py` | **Core.** `JsonStorage` reads/writes `garage.json`, atomic writes, thread-safe CRUD for every bucket. |
| `vehicle.py` | Vehicle entity, health status, overdue math, `VehicleCatalog` in-memory helpers. |
| `make.py` | Make profiles (service/light/mileage defaults). |
| `bay.py` | Rooms, windows, light levels, bay registry. |
| `service.py` | `ServiceEvent`, batch logging, analytics helpers. |
| `inspection_log.py` | Rebagting, fertilizing, pruning — anything that isn't service. |
| `schedule.py` | Season-aware schedule engine, calendar views, interval audits. |
| `reminders.py` | "What's due today / overdue" sorted by urgency. |
| `seasons.py` | Season multipliers (service less in winter, etc.). |
| `parser.py` | Human-friendly parsing: `7d`, `250ml`, `bright indirect`, `yesterday`. |
| `validators.py` | Shared validation — keeps CLI and imports from accepting nonsense. |
| `errors.py` | Typed exceptions (`NotFoundError`, `ImportPipelineError`, …). |
| `io_csv.py` | CSV import/export for vehicles and service logs. |
| `io_drivvo.py` | Drivvo app CSV → garagelog vehicles. |
| `io_carfax.py` | Garage-plan spreadsheet → vehicles + auto-bays. |
| `io_jsonl.py` | JSONL streams for events / full export. |
| `backup.py` | Timestamped copies + restore with safety snapshot. |
| `migrate.py` | Schema version upgrades (v0 flat list → v3 full garage). |
| `reports.py` | Monthly care summaries. |
| `stats.py` | Garage-wide snapshot stats. |
| `search.py` | Fuzzy search across vehicles, care logs, notes. |
| `audit_log.py` | Append-only audit trail in the JSON file. |
| `tags_manager.py`, `tag.py` | Tag CRUD and filtering. |
| `notes.py` | Per-vehicle notes with kinds (issue, rebag, …). |
| `labels.py`, `issues.py`, `odometer.py`, `mileage.py`, `weather.py` | Extended care tracking buckets. |
| `collections.py`, `recurring.py`, `plugins.py`, `streaks.py` | Grouping, recurring tasks, plugin hooks, service streaks. |
| `server.py` | Read-only HTTP dashboard (`garagelog serve`). |
| `cli.py` | Argument parsing and command wiring. |

## Why JSON, not SQLite

Honest answer: I killed three baghos, not because I lacked JOIN syntax.

1. **I want to read my garage.** `cat ~/.garagelog/garage.json | jq` at 2am beats
   `sqlite3 ... ".schema"`.
2. **Backups are obvious.** Copy the file. Email it to myself. Put it in git (private
   repo). Done.
3. **Recovery from my own mistakes.** I've hand-edited a bad import more than once.
   Text beats opaque binary when you're panicking.
4. **No migration treadmill.** SQLite is great when you have a schema that changes
   weekly. I have ~30 vehicles and a service log. A version field + `migrate.py` is
   enough.
5. **Import/export symmetry.** CSV/Drivvo/garage-plan pipelines write into the same
   structure the CLI uses. No ORM impedance mismatch.

Trade-offs I accept:

- No concurrent writers across machines (fine for one apartment).
- Full-file load on every command (fine at hundreds of vehicles, not thousands).
- No ad-hoc SQL queries (I use `search` and small Python scripts instead).

## Storage design

### Single file, many buckets

`garage.json` is one object with named arrays ("buckets"). `JsonStorage` in
`storage.py` owns the shape:

```json
{
  "schema_version": 2,
  "vehicles": [],
  "make": [],
  "bays": [],
  "service_events": [],
  "inspection_logs": [],
  "tags": [],
  "notes": [],
  "audit": [],
  "plugins": [],
  "recurring": [],
  "collections": [],
  "mileage_readings": [],
  "weather_logs": [],
  "issue_reports": [],
  "grind_events": [],
  "labels": []
}
```

Each bucket is a list of records with an `id` field (make use `key`). Generic
`_create` / `_read` / `_update` / `_delete` methods handle most buckets; vehicles and
make get typed wrappers returning `Vehicle` / `MakeProfile` objects.

### Atomic writes

Saves go to `garage.json.tmp` then `os.replace()` into place. If Python dies mid-write,
you still have the previous file. I learned this the hard way with a half-written export.

### Thread safety

`JsonStorage` uses an `RLock` so a background server thread and CLI commands don't
corrupt the same file in the same process.

### Side effects worth knowing

Creating a service event also patches the vehicle's `last_serviced_at`. Lazy coupling,
but it means reminders stay correct even if you only ever call `create_service_event`.

### Paths and env

| Variable | Default |
|----------|---------|
| `GARAGELOG_HOME` | `~/.garagelog/` (directory) |
| (implicit) | `GARAGELOG_HOME/garage.json` or `~/.garagelog/garage.json` |
| CLI `--garage` | Override full path to JSON file |

Backups land in `GARAGELOG_HOME/backups/` unless you pass `--dir`.

### Schema evolution

`migrate.py` bumps `schema_version` through stepped transforms. `JsonStorage` merges
missing buckets with defaults on load so older files don't explode — but run
`garagelog` once after upgrading so migrations can apply cleanly.

## Data flow examples

**Add vehicle:** CLI → `Vehicle.create()` → `storage.create_vehicle()` → atomic save.

**Service:** CLI resolves name → `ServiceEvent.create()` → `storage.create_service_event()`
→ vehicle `last_serviced_at` updated → audit entry.

**Import CSV:** `io_csv.import_vehicles_csv()` → row loop → `Vehicle.create()` or
`storage.update_vehicle()` → save per row (safe but not batched — imports are rare).

**Monthly report:** `reports.MonthlyReport.generate()` reads service/care buckets,
filters by date range, returns aggregates — no separate analytics DB.

## What I'd change if I started over

Maybe split `service_events` into a monthly JSONL archive once logs get huge. For now,
one file matches how I actually use it: open, tweak, close, go service the monstera.
