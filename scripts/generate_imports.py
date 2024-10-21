#!/usr/bin/env python3
"""Generate multi-source import fixtures for garagelog (stdlib only)."""
from __future__ import annotations

import csv
import json
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "imports"

SOURCES = [
    "drivvo", "carfax", "csv_native", "jsonl_events",
    "blossom", "vera", "flora", "fleetio",
]
YEARS = list(range(2019, 2026))


def _rng(source: str, year: int, month: int) -> random.Random:
    return random.Random(hash((source, year, month)) & 0xFFFFFFFF)


def _plant_rows(rng: random.Random, n: int) -> list[dict]:
    rows = []
    for i in range(n):
        d = date(rng.randint(2019, 2025), rng.randint(1, 12), rng.randint(1, 28))
        rows.append({
            "name": f"Plant {i}",
            "species": rng.choice(["Pothos", "Monstera", "Snake Plant", "ZZ Plant"]),
            "room": rng.choice(["Kitchen", "Bedroom", "Office", "Living Room"]),
            "interval_days": rng.choice([5, 7, 10, 14]),
            "last_watered": d.isoformat(),
            "notes": "x" * rng.randint(0, 20),
        })
    return rows


def _write_drivvo_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "Plant Name", "Species", "Room", "Water Every (days)",
        "Last Watered", "Notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "Plant Name": r["name"],
                "Species": r["species"],
                "Room": r["room"],
                "Water Every (days)": r["interval_days"],
                "Last Watered": r["last_watered"],
                "Notes": r["notes"],
            })


def _write_native_csv(path: Path, rows: list[dict]) -> None:
    fields = ["name", "species_key", "location", "water_interval_days", "last_watered", "notes"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "name": r["name"],
                "species_key": r["species"].lower().replace(" ", "-"),
                "location": r["room"],
                "water_interval_days": r["interval_days"],
                "last_watered": r["last_watered"],
                "notes": r["notes"],
            })


def _write_carfax_csv(path: Path, rows: list[dict]) -> None:
    fields = ["bed", "section", "row", "plant_name", "species", "quantity", "notes"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows):
            qty_rng = random.Random(i)
            w.writerow({
                "bed": f"Bed-{i % 4 + 1}",
                "section": r["room"],
                "row": str(i % 6 + 1),
                "plant_name": r["name"],
                "species": r["species"],
                "quantity": str(qty_rng.randint(1, 3)),
                "notes": r["notes"],
            })


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = []
    for r in rows:
        lines.append(json.dumps({"type": "watering", "plant": r["name"], "date": r["last_watered"]}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_generic_json(path: Path, source: str, rows: list[dict]) -> None:
    path.write_text(
        json.dumps({"source": source, "version": 1, "plants": rows}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    total_files = 0
    for source in SOURCES:
        for year in YEARS:
            src_dir = OUT / source / str(year)
            src_dir.mkdir(parents=True, exist_ok=True)
            for month in range(1, 13):
                rng = _rng(source, year, month)
                rows = _plant_rows(rng, rng.randint(15, 45))
                stem = f"{source}_{year}_{month:02d}"
                if source == "drivvo":
                    _write_drivvo_csv(src_dir / f"{stem}.csv", rows)
                elif source == "csv_native":
                    _write_native_csv(src_dir / f"{stem}.csv", rows)
                elif source == "carfax":
                    _write_carfax_csv(src_dir / f"{stem}.csv", rows)
                elif source == "jsonl_events":
                    _write_jsonl(src_dir / f"{stem}.jsonl", rows)
                else:
                    if month % 3 == 0:
                        _write_drivvo_csv(src_dir / f"{stem}.csv", rows)
                    elif month % 3 == 1:
                        _write_generic_json(src_dir / f"{stem}.json", source, rows)
                    else:
                        _write_native_csv(src_dir / f"{stem}.csv", rows)
                total_files += 1
    print(f"wrote {total_files} import fixtures under {OUT}")


if __name__ == "__main__":
    main()
