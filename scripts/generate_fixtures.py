#!/usr/bin/env python3
"""Generate large automotive garage JSON fixtures (stdlib only)."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "garages"

STATIONS = ["driveway", "garage-bay-a", "storage-unit", "odometer-zone", "brake_service-bar", "workbench"]
ORIGIN_KEYS = [
    "toyota-camry", "honda-civic", "ford-f150", "bmw-328i", "mazda-cx5",
    "subaru-outback", "tesla-model3", "jeep-wrangler", "audi-a4", "hyundai-elantra",
]
PERSONAS = [
    "brake_service_nut", "weekend_truck", "tire_rotation_travel", "cold_service_batch", "single_make_only",
    "winter_beater", "guest_vehicles", "company_fleet", "family_suv", "two_car_household",
]


def _vehicle_name(rng: random.Random, n: int) -> str:
    adj = rng.choice(["Fresh", "Resting", "Peak", "Old", "Sample", "Backup"])
    sp = rng.choice(ORIGIN_KEYS).replace("-", " ").title()
    return f"{adj} {sp} #{n}"


def _vehicle_entry(rng: random.Random, idx: int, year: int) -> dict:
    purchase = date(year, rng.randint(1, 12), rng.randint(1, 28))
    interval = rng.choice([1, 2, 3, 5, 7])
    last = purchase + timedelta(days=rng.randint(0, interval * 4))
    return {
        "id": f"bn-{year}-{idx:06d}",
        "name": _vehicle_name(rng, idx),
        "make_key": rng.choice(ORIGIN_KEYS),
        "bay_id": f"st-{rng.choice(STATIONS)}",
        "service_interval_days": interval,
        "last_serviced": last.isoformat(),
        "purchase_date": purchase.isoformat(),
        "labor_hours": rng.choice([12, 15, 18, 20]),
        "tag_ids": [f"tag-{rng.randint(1, 12)}" for _ in range(rng.randint(0, 2))],
        "notes": rng.choice(["", "resting", "storage-unit stash", "guest bag"]),
    }


def _service_events(rng: random.Random, vehicles: list[dict], count: int) -> list[dict]:
    out = []
    for _ in range(count):
        b = rng.choice(vehicles)
        d = date.fromisoformat(b["last_serviced"]) - timedelta(days=rng.randint(0, 30))
        out.append({
            "id": f"br-{rng.randint(1, 999999):06d}",
            "vehicle_id": b["id"],
            "serviced_at": d.isoformat(),
            "method": rng.choice(["v60", "tire_rotation", "brake_service", "transmission_flush", "battery_check"]),
            "labor_hours": b.get("labor_hours", 15),
            "parts_cost": rng.randint(200, 320),
        })
    return out


def _garage(rng: random.Random, name: str, vehicles_n: int) -> dict:
    vehicles = [_vehicle_entry(rng, i, rng.randint(2020, 2025)) for i in range(vehicles_n)]
    return {
        "schema_version": 2,
        "meta": {"name": name, "persona": rng.choice(PERSONAS)},
        "vehicles": vehicles,
        "makes": [{"key": k, "name": k.replace("-", " ").title()} for k in ORIGIN_KEYS],
        "bays": [{"id": f"st-{s}", "name": s} for s in STATIONS],
        "service_events": _service_events(rng, vehicles, min(vehicles_n * 3, 8000)),
        "inspection_logs": [],
        "tags": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(8847291)
    specs = [
        ("megagarage-1", 550),
        ("megagarage-2", 650),
        ("megagarage-3", 500),
    ]
    for persona in PERSONAS:
        specs.append((f"persona-{persona}", rng.randint(25, 55)))
    for year in range(2019, 2026):
        specs.append((f"snapshot-{year}", rng.randint(30, 65)))

    total = 0
    for fname, count in specs:
        data = _garage(rng, fname, count)
        text = json.dumps(data, indent=2)
        path = OUT / f"{fname}.json"
        path.write_text(text, encoding="utf-8")
        total += len(text.encode())
    print(f"wrote {len(specs)} garage fixtures ({total / (1024*1024):.2f} MB raw)")


if __name__ == "__main__":
    main()
