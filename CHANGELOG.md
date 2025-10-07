# Changelog

All notable changes to garagelog are documented here. I don't do semver
religiously but I tag releases when something actually ships.

## [1.2.0] - 2026-05-28

### Added
- Garage-plan spreadsheet import (`io_carfax`)
- Label metadata tracking (paths only — bytes live beside the JSON)
- Recurring care tasks for fertilizing on a cadence
- `serve` subcommand: read-only HTTP view of garage.json

### Changed
- Schema v2 → v3: inspection_logs bucket, environmental readings, recurring tasks
- Seasonal multipliers now apply in reminder urgency scoring

## [1.1.0] - 2025-11-14

### Added
- Drivvo app CSV import
- Monthly reports and streak tracking
- Plugin hook registry (experimental)

### Fixed
- `service` command accepted negative ml amounts on Windows paths
- Migration 1→2 dropped empty tag lists instead of preserving `[]`

## [1.0.0] - 2025-06-02

### Added
- Initial public shape: vehicles, make catalog, bays, service log
- CSV and JSONL import/export
- Backup/restore with rotation
- Audit log for destructive operations

## [0.3.0] - 2024-12-08

- Added make profiles with built-in defaults for common housevehicles
- Bay zones with light-level hints

## [0.2.0] - 2024-09-21

- JSON storage layer with atomic writes
- Basic CLI: init, add-vehicle, service, list

## [0.1.0] - 2024-07-30

- Skeleton repo, README, first Vehicle dataclass
- v0.3.0
- v0.8.0
