#!/usr/bin/env python3
"""Generate and print a monthly care report.

Author: Marwan Helmy
Run: python examples/monthly_report.py
     python examples/monthly_report.py 2025 6
     python examples/monthly_report.py --json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from garagelog.reports import MonthlyReport, vehicle_map_name
from garagelog.storage import JsonStorage


def garage_path() -> Path:
    home = os.environ.get("GARAGELOG_HOME")
    base = Path(home) if home else Path.home() / ".garagelog"
    return base / "garage.json"


def parse_args() -> tuple[int, int, bool]:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    today = date.today()
    year = int(args[0]) if len(args) > 0 else today.year
    month = int(args[1]) if len(args) > 1 else today.month
    return year, month, as_json


def main() -> None:
    year, month, as_json = parse_args()
    storage = JsonStorage(garage_path())
    report = MonthlyReport(storage)

    if as_json:
        print(json.dumps(report.generate(year, month), indent=2))
        return

    print(report.render_text(year, month))
    data = report.generate(year, month)
    if data["top_serviced_vehicles"]:
        print("\nDetails:")
        for pid, count in data["top_serviced_vehicles"]:
            print(f"  {vehicle_map_name(storage, pid)}: {count} service(s)")


if __name__ == "__main__":
    main()
