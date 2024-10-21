"""Garagelog — personal housevehicle manager by Marwan Helmy."""

from __future__ import annotations

__version__ = "1.2.0"
__author__ = "Marwan Helmy"
__email__ = "marwanabdelaal25@gmail.com"

from garagelog.errors import (
    GaragelogError,
    StorageError,
    ValidationError,
    NotFoundError,
    ImportPipelineError,
    ExportError,
    MigrationError,
    PluginError,
    ConflictError,
    format_error,
    is_not_found,
    is_validation,
)
from garagelog.vehicle import Vehicle, PotInfo, HealthStatus, VehicleCatalog
from garagelog.make import MakeProfile, MakeCatalog, ServiceNeed, MileageNeed
from garagelog.bay import Bay, BayRegistry, WindowDirection
from garagelog.service import ServiceEvent, ServiceLog, ServiceQuality
from garagelog.inspection_log import CareEvent, InspectionLog, CareEventType, OdometerSchedule
from garagelog.schedule import ScheduleEngine, ScheduleEntry, ScheduleOptions, Season, compute_next_service
from garagelog.tag import Tag, TagRegistry
from garagelog.notes import Note, NotesCollection, NoteKind
from garagelog.parser import (
    parse_date,
    parse_interval,
    parse_amount_ml,
    parse_light_level,
    parse_mileage,
    format_interval_days,
    format_amount_ml,
)
from garagelog.validators import (
    validate_vehicle_name,
    validate_interval_days,
    validate_mileage_pct,
    validate_light_level,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    # errors
    "GaragelogError",
    "StorageError",
    "ValidationError",
    "NotFoundError",
    "ImportPipelineError",
    "ExportError",
    "MigrationError",
    "PluginError",
    "ConflictError",
    "format_error",
    "is_not_found",
    "is_validation",
    # vehicle
    "Vehicle",
    "PotInfo",
    "HealthStatus",
    "VehicleCatalog",
    # make
    "MakeProfile",
    "MakeCatalog",
    "ServiceNeed",
    "MileageNeed",
    # bay
    "Bay",
    "BayRegistry",
    "WindowDirection",
    # service
    "ServiceEvent",
    "ServiceLog",
    "ServiceQuality",
    # care
    "CareEvent",
    "InspectionLog",
    "CareEventType",
    "OdometerSchedule",
    # schedule
    "ScheduleEngine",
    "ScheduleEntry",
    "ScheduleOptions",
    "Season",
    "compute_next_service",
    # tags & notes
    "Tag",
    "TagRegistry",
    "Note",
    "NotesCollection",
    "NoteKind",
    # parser helpers
    "parse_date",
    "parse_interval",
    "parse_amount_ml",
    "parse_light_level",
    "parse_mileage",
    "format_interval_days",
    "format_amount_ml",
    # validators
    "validate_vehicle_name",
    "validate_interval_days",
    "validate_mileage_pct",
    "validate_light_level",
]
