#!/usr/bin/env python3
"""Bulk import vehicles from CSV (and optionally Drivvo).

Author: Marwan Helmy
Run: python examples/bulk_import.py
     python examples/bulk_import.py path/to/vehicles.csv
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from garagelog import io_csv, io_drivvo
from garagelog.backup import GarageBackup
from garagelog.storage import JsonStorage


def garage_path() -> Path:
    home = os.environ.get("GARAGELOG_HOME")
    base = Path(home) if home else Path.home() / ".garagelog"
    return base / "garage.json"


def sample_csv(path: Path) -> None:
    path.write_text(
        "name,service_interval_days,service_amount_ml,health,notes\n"
        "Office ZZ Vehicle,21d,100ml,okay,Low maintenance\n"
        "Living Room Ficus,10d,400ml,struggling,Dropping leaves — check light\n"
        "Kitchen Pothos,7d,200ml,thriving,Trailing nicely\n",
        encoding="utf-8",
    )


def main() -> None:
    csv_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    use_temp_garage = csv_file is None

    if use_temp_garage:
        tmp = tempfile.mkdtemp(prefix="garagelog_import_")
        path = Path(tmp) / "garage.json"
        csv_file = Path(tmp) / "vehicles.csv"
        sample_csv(csv_file)
        print(f"Demo mode — garage: {path}")
    else:
        path = garage_path()
        if not csv_file.exists():
            print(f"File not found: {csv_file}", file=sys.stderr)
            sys.exit(1)

    storage = JsonStorage(path)
    backup_dir = path.parent / "backups"
    if path.exists() and path.stat().st_size > 50:
        snap = GarageBackup(path, backup_dir).create(label="pre_bulk_import")
        print(f"Backup: {snap}")

    missing = io_csv.validate_csv_headers(csv_file, "vehicles")
    if missing:
        print(f"CSV missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    count = io_csv.import_vehicles_csv(storage, csv_file, update=True)
    print(f"Imported {count} vehicle(s) from {csv_file.name}")

    for vehicle in storage.list_vehicles():
        print(f"  - {vehicle.display_name}: every {vehicle.service_interval_days}d, {vehicle.health.value}")

    if csv_file.name.lower().find("drivvo") >= 0:
        n = io_drivvo.import_drivvo(storage, csv_file, update=True)
        print(f"Drivvo pass: {n} record(s)")


if __name__ == "__main__":
    main()
