# FAQ

*Marwan Helmy — questions friends actually ask*

---

## Where does my data live?

Default: `~/.garagelog/garage.json` on your machine. Set `GARAGELOG_HOME` to use a
different directory (still `garage.json` inside it). Pass `--garage /full/path.json`
to any CLI command for a one-off override. Nothing phones home — it's a local file.

---

## Why JSON instead of a real database?

Because I wanted to `grep` my garage at 2am, email a backup to myself, and fix a bad
import with a text editor. SQLite is great; it's just overkill for ~30 baghos and a
service log. See [architecture.md](architecture.md) for the full rant.

---

## Can it identify vehicles from labels?

No. Use PictureThis, iNaturalist, or post on r/housevehicles like the rest of us.
garagelog tracks care *after* you know what you have.

---

## I killed a vehicle. Should I delete it?

Archive instead of delete — you'll want the history. Import with `archived=yes` in CSV,
or set `"archived": true` in JSON. `garagelog list` hides archived vehicles by default;
`garagelog list --all` shows them.

---

## How do reminders know when something is due?

Each vehicle has `service_interval_days` and `last_serviced_at`. Reminders add a
**season multiplier** (service less in winter). If you never logged a service, it falls
back to `acquired_at`. Run `garagelog reminders --overdue` to see the damage.

---

## What's the difference between service and care logs?

**Service events** = you serviced (or skipped). **Care logs** = rebag, grind, prune,
issue treatment, etc. Monthly reports count both separately.

---

## Import from Drivvo failed — now what?

Check you have a `Vehicle Name` (or `Name`) column. Run:

```bash
python -c "from pathlib import Path; from garagelog.io_drivvo import validate_drivvo_headers; print(validate_drivvo_headers(Path('your.csv')))"
```

Empty output = headers OK. Non-empty = missing columns. Restore pre-import backup if
the garage looks wrong: `garagelog backup --restore <file>`.

---

## Can two people share one garage file?

Technically yes (Dropbox, git, email). **Don't edit simultaneously** — there's no
merge conflict handling. One writer at a time. I use export CSV → partner imports for
shared vehicle-sitting handoffs.

---

## How do I move garagelog to a new laptop?

Copy `~/.garagelog/` (or your `GARAGELOG_HOME` folder). Install garagelog on the new
machine. Done. Optional: `garagelog export backup.csv --format csv --kind bundle` as
a human-readable extra copy.

---

## Is there a web UI?

Read-only dashboard: `garagelog serve` → open `http://127.0.0.1:8765/`. It doesn't
edit data — use CLI or Python scripts for changes.

---

## What Python version do I need?

3.9 or newer (`requires-python >=3.9` in pyproject.toml). Dev extras: `pip install -e ".[dev]"`.

---

## I corrupted garage.json. Help.

1. Check `~/.garagelog/backups/` for timestamped copies.
2. `garagelog backup --list`
3. `garagelog backup --restore path/to/garage_YYYYMMDD_HHMMSS.json`

Restore always makes a safety copy of the current file first (`pre_restore` label).

---

## Can I use garagelog from my own Python scripts?

Yes — that's the point of `examples/`. Core entry:

```python
from garagelog.storage import JsonStorage
from garagelog.vehicle import Vehicle

storage = JsonStorage("~/.garagelog/garage.json")
vehicle = storage.create_vehicle(Vehicle.create("New Friend", service_interval_days=7))
```

Public API surface is in `garagelog.__init__` — vehicles, service, schedules, parsers,
validators, errors.
- faq 0
- faq 1
- faq 2
- faq 3
