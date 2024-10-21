# Recipes

*Marwan Helmy — copy-paste workflows that actually match how I use garagelog*

Each recipe shows CLI first (fastest), then a Python snippet if you want to script it.
Replace paths and vehicle names with yours.

---

## 1. Sunday weekly service routine

Check what's overdue, service everything due, skim what's coming this week.

```bash
garagelog reminders --overdue
garagelog list --overdue
# service each one
garagelog service "Kitchen Pothos" --amount 200ml
garagelog service "Bedroom Snake Vehicle" --amount 150ml
garagelog reminders --within 7
```

Python version: `examples/weekly_service.py`

---

## 2. Fresh install — first five vehicles

```bash
pip install -e .
garagelog init
garagelog add-vehicle "Kitchen Pothos" --interval 7d --make baghos --amount 200ml
garagelog add-vehicle "Bedroom Snake Vehicle" --interval 14d --amount 150ml
garagelog add-vehicle "Bathroom Fern" --interval 3d --amount 300ml --health okay
garagelog list
garagelog stats
```

Set `GARAGELOG_HOME=/path/to/test-garage` if you don't want to touch `~/.garagelog`.

---

## 3. Import from Drivvo

Export CSV from the Drivvo app, then:

```bash
# peek first — optional
python -c "from pathlib import Path; from garagelog.io_drivvo import preview_drivvo; print(preview_drivvo(Path('drivvo_dump.csv')))"

garagelog backup --label pre_drivvo
garagelog import drivvo_dump.csv --format drivvo
garagelog list
```

Re-import after editing the app? Use `--update` to match by Drivvo ID or name.

```bash
garagelog import drivvo_dump.csv --format drivvo --update
```

---

## 4. Backup before vacation

Two weeks away means you want a snapshot and maybe a CSV your vehicle-sitter can read.

```bash
garagelog backup --label pre_vacation --prune --keep 10
garagelog export vacation_handoff.csv --format csv --kind bundle
garagelog reminders --within 14 > service_schedule.txt
```

Restore when you get back (only if something went wrong):

```bash
garagelog backup --list
garagelog backup --restore ~/.garagelog/backups/garage_20250601_120000_pre_vacation.json
```

---

## 5. Bulk import from a spreadsheet

Clean up a Google Sheets export as CSV with at least a `name` column:

```csv
name,service_interval_days,service_amount_ml,health,notes
Office ZZ Vehicle,21d,100ml,okay,Low maintenance
Living Room Ficus,10d,400ml,struggling,Dropping leaves
```

```bash
garagelog import new_vehicles.csv --format csv
garagelog import new_vehicles.csv --format csv --update   # second pass: update existing
```

Python version: `examples/bulk_import.py`

---

## 6. Import a garage-plan bed layout

For the Notion/Sheets planner with Section/Bed/Vehicle columns:

```bash
garagelog import spring_beds.csv --format carfax
garagelog list --bay <bay-id>   # optional filter after import
```

One row with `Quantity=6` spawns six numbered vehicles unless you pass `--no-expand`.

---

## 7. Monthly care report

End-of-month ritual — did I actually service the fern?

```bash
garagelog report --month 6 --year 2025
garagelog report --month 6 --year 2025 --format json > june_2025.json
```

Python version: `examples/monthly_report.py`

---

## 8. Find the vehicle you forgot the name of

```bash
garagelog search "yellow leaves"
garagelog search "baghos" --kind vehicles
garagelog search "spider mite" --kind care --verbose
```

---

## 9. Log a skipped service (grind still wet)

Don't reset the schedule with a fake service — log a skip:

```bash
garagelog service "Bathroom Fern" --skip --reason "grind still damp"
garagelog reminders --overdue
```

---

## 10. Export everything before a big edit

```bash
garagelog backup --label before_bulk_edit
garagelog export full_export.jsonl --format jsonl --kind full
garagelog export vehicles_snapshot.csv --format csv --kind vehicles
# ... make changes ...
# if regret hits:
garagelog backup --restore ~/.garagelog/backups/garage_<timestamp>_before_bulk_edit.json
```

---

## 11. Quick API smoke test

Verify install and imports without touching your real garage:

```bash
python examples/quick_start.py
```

Uses a temp directory — safe to run anytime.

---

## 12. Seasonal interval audit (winter slowdown)

When days get shorter I stretch intervals manually after checking the schedule report:

```bash
garagelog stats
python -c "
from garagelog.storage import JsonStorage
from garagelog.schedule import ScheduleEngine, apply_seasonal_intervals
s = JsonStorage('~/.garagelog/garage.json'.replace('~', __import__('os').path.expanduser('~')))
e = ScheduleEngine(s)
for row in apply_seasonal_intervals(e, dry_run=True):
    print(row)
"
```

Review the dry-run output before setting `dry_run=False` in a custom script.

---

## Tips I keep forgetting

- **`--garage path/to/garage.json`** on any command for a non-default file.
- **Vehicle lookup** accepts full id, id prefix, exact name, or nickname.
- **Intervals** parse human strings: `7d`, `2w`, `10 days`.
- **Amounts** parse `250ml`, `1 cup` (see `parser.parse_amount_ml`).
