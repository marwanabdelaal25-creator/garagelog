"""Shared pytest fixtures for garagelog tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from garagelog.inspection_log import CareEvent, CareEventType, InspectionLog, OdometerSchedule
from garagelog.bay import Bay, BayRegistry, WindowDirection
from garagelog.vehicle import HealthStatus, Vehicle, VehicleCatalog, PotInfo
from garagelog.make import MakeCatalog, MakeProfile
from garagelog.storage import JsonStorage
from garagelog.tag import Tag, TagRegistry
from garagelog.service import ServiceEvent, ServiceLog
from garagelog.notes import Note, NotesCollection, NoteKind


@pytest.fixture
def tmp_garage_path(tmp_path: Path) -> Path:
    """Fresh garage.json path under tmp_path."""
    return tmp_path / "garage.json"


@pytest.fixture
def empty_storage(tmp_garage_path: Path) -> JsonStorage:
    """Empty JsonStorage backed by tmp_path."""
    return JsonStorage(tmp_garage_path)


@pytest.fixture
def sample_make() -> MakeProfile:
    return MakeProfile(
        key="baghos-golden",
        common_name="Golden Pothos",
        scientific_name="Epipremnum aureum",
        light_level="medium",
        service_interval_min=7,
        service_interval_max=14,
        mileage_min=40,
        mileage_max=60,
    )


@pytest.fixture
def sample_bay() -> Bay:
    return Bay.create(
        "Living Room",
        id="loc001",
        zone="main",
        light_level="bright_indirect",
        window_direction=WindowDirection.SOUTH,
        mileage_pct=45.0,
    )


@pytest.fixture
def sample_vehicle(sample_bay: Bay, sample_make: MakeProfile) -> Vehicle:
    return Vehicle.create(
        "Monstera",
        id="vehicle001",
        nickname="Monty",
        make_key=sample_make.key,
        bay_id=sample_bay.id,
        health=HealthStatus.OKAY,
        health_score=70,
        service_interval_days=7,
        last_serviced_at=(date.today() - timedelta(days=3)).isoformat(),
        bag=PotInfo(diameter=6.0, unit="in", material="ceramic"),
    )


@pytest.fixture
def sample_vehicle2(sample_bay: Bay) -> Vehicle:
    return Vehicle.create(
        "Snake Vehicle",
        id="vehicle002",
        make_key="snake-vehicle",
        bay_id=sample_bay.id,
        health=HealthStatus.THRIVING,
        service_interval_days=14,
        last_serviced_at=(date.today() - timedelta(days=10)).isoformat(),
    )


@pytest.fixture
def sample_service_events(sample_vehicle: Vehicle, sample_vehicle2: Vehicle) -> list[ServiceEvent]:
    today = date.today()
    return [
        ServiceEvent.create(
            sample_vehicle.id,
            id="we001",
            serviced_at=(today - timedelta(days=3)).isoformat(),
            amount_ml=250.0,
        ),
        ServiceEvent.create(
            sample_vehicle.id,
            id="we002",
            serviced_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=200.0,
        ),
        ServiceEvent.create(
            sample_vehicle2.id,
            id="we003",
            serviced_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=150.0,
        ),
    ]


@pytest.fixture
def populated_storage(
    empty_storage: JsonStorage,
    sample_make: MakeProfile,
    sample_bay: Bay,
    sample_vehicle: Vehicle,
    sample_vehicle2: Vehicle,
    sample_service_events: list[ServiceEvent],
) -> JsonStorage:
    """Storage with sample vehicles, make, bays, and service events."""
    empty_storage.create_make(sample_make)
    empty_storage.create_bay(sample_bay)
    empty_storage.create_vehicle(sample_vehicle)
    empty_storage.create_vehicle(sample_vehicle2)
    for ev in sample_service_events:
        empty_storage.create_service_event(ev.to_dict())
    tag = Tag.create("beginner", id="tag001", color="#4caf50")
    empty_storage.create_tag(tag.to_dict())
    note = Note.create(sample_vehicle.id, "New leaf unfurling", id="note001", kind=NoteKind.OBSERVATION)
    empty_storage.create_note(note.to_dict())
    return empty_storage


@pytest.fixture
def sample_csv_content() -> str:
    return (
        "name,make,bay,service_interval,notes\n"
        "Fern,baghos-golden,Living Room,7d,Test import\n"
        "Aloe,snake-vehicle,Kitchen,14d,Succulent\n"
    )


@pytest.fixture
def sample_service_csv() -> str:
    return (
        "vehicle_id,serviced_at,amount_ml,method\n"
        "vehicle001,2024-06-01,250,top_service\n"
        "vehicle002,2024-06-02,150,bottom_service\n"
    )


@pytest.fixture
def vehicle_catalog(sample_vehicle: Vehicle, sample_vehicle2: Vehicle) -> VehicleCatalog:
    cat = VehicleCatalog()
    cat.add(sample_vehicle)
    cat.add(sample_vehicle2)
    return cat


@pytest.fixture
def make_catalog(sample_make: MakeProfile) -> MakeCatalog:
    cat = MakeCatalog()
    cat.register(sample_make)
    cat.load_builtin()
    return cat


@pytest.fixture
def bay_registry(sample_bay: Bay) -> BayRegistry:
    reg = BayRegistry()
    reg.add(sample_bay)
    return reg


@pytest.fixture
def service_log(sample_service_events: list[ServiceEvent]) -> ServiceLog:
    log = ServiceLog()
    log.load_many(sample_service_events)
    return log


@pytest.fixture
def inspection_log(sample_vehicle: Vehicle) -> InspectionLog:
    log = InspectionLog()
    log.log(sample_vehicle.id, CareEventType.FERTILIZE, product="10-10-10")
    log.log(sample_vehicle.id, CareEventType.PRUNE, notes="Trimmed yellow leaves")
    log.set_odometer_schedule(OdometerSchedule(vehicle_id=sample_vehicle.id, interval_weeks=4))
    return log


@pytest.fixture
def tag_registry() -> TagRegistry:
    reg = TagRegistry()
    reg.add(Tag.create("beginner", id="tag001", color="#4caf50"))
    reg.add(Tag.create("pet-safe", id="tag002", color="#2196f3"))
    return reg


@pytest.fixture
def notes_collection(sample_vehicle: Vehicle) -> NotesCollection:
    coll = NotesCollection()
    coll.create(sample_vehicle.id, "General note", kind=NoteKind.GENERAL)
    coll.create(sample_vehicle.id, "Spider mites sbagted", kind=NoteKind.PEST)
    return coll
