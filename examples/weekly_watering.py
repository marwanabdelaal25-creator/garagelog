#!/usr/bin/env python3
"""Weekly service workflow — service overdue and due-today vehicles.

Author: Marwan Helmy
Run: python examples/weekly_service.py
     GARAGELOG_HOME=~/.garagelog python examples/weekly_service.py
"""

from __future__ import annotations

import os
from pathlib import Path

from garagelog.reminders import ReminderEngine
from garagelog.storage import JsonStorage
from garagelog.service import ServiceEvent


def garage_path() -> Path:
    home = os.environ.get("GARAGELOG_HOME")
    base = Path(home) if home else Path.home() / ".garagelog"
    return base / "garage.json"


def main() -> None:
    storage = JsonStorage(garage_path())
    engine = ReminderEngine(storage)
    due = [r for r in engine.upcoming(within_days=0, include_overdue=True) if r.urgency != "upcoming"]

    if not due:
        print("All caught up — nothing due today or overdue.")
        return

    print(f"Service {len(due)} vehicle(s):\n")
    for rem in due:
        vehicle = storage.get_vehicle(rem.vehicle_id)
        amount = vehicle.service_amount_ml
        flag = "OVERDUE" if rem.urgency == "overdue" else "TODAY"
        print(f"  [{flag}] {rem.vehicle_name} (due {rem.due_at.date()})")

        if amount is None:
            print("    skipped — no default amount; set service_amount_ml on vehicle")
            continue

        event = ServiceEvent.create(vehicle_id=vehicle.id, amount_ml=amount, notes="weekly script")
        storage.create_service_event(event.to_dict())
        print(f"    logged: {event.summary()}")

    print("\nDone. Run `garagelog reminders --within 7` to preview the week ahead.")


if __name__ == "__main__":
    main()
