#!/usr/bin/env python3
"""Smoke test — temp garage, add vehicle, log service, check reminders.

Author: Marwan Helmy
Run: python examples/quick_start.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from garagelog.vehicle import Vehicle
from garagelog.reminders import ReminderEngine
from garagelog.storage import JsonStorage
from garagelog.service import ServiceEvent


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "garage.json"
        storage = JsonStorage(path)
        vehicle = Vehicle.create("Test Pothos", service_interval_days=7, source="example")
        created = storage.create_vehicle(vehicle)
        event = ServiceEvent.create(vehicle_id=created.id, amount_ml=200)
        storage.create_service_event(event.to_dict())
        overdue = ReminderEngine(storage).overdue_only()
        print("garage:", path)
        print("vehicle:", created.display_name, f"({created.id})")
        print("serviced:", event.summary())
        print("overdue:", len(overdue))
        assert storage.get_vehicle(created.id).name == "Test Pothos"
        print("smoke test passed")


if __name__ == "__main__":
    main()
