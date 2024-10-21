# Data formats

*Marwan Helmy — what goes in, what comes out*

garagelog speaks a few dialects. The source of truth is always `garage.json`; everything
else is a view or an import path into that file.

---

## garage.json schema

**Bay:** `~/.garagelog/garage.json` (or `$GARAGELOG_HOME/garage.json`)

**Root object fields:**

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Currently `2` in storage defaults; migrations may bump to `3`. |
| `vehicles` | array | Your vehicles. |
| `make` | array | Reusable make profiles. |
| `bays` | array | Rooms / zones. |
| `service_events` | array | Append-style service log. |
| `inspection_logs` | array | Rebag, grind, prune, etc. |
| `tags` | array | Label definitions. |
| `notes` | array | Free-form notes linked to vehicles. |
| `audit` | array | Who changed what (CLI writes here). |
| `plugins` | array | Plugin config blobs. |
| `recurring` | array | Recurring care tasks. |
| `collections` | array | Vehicle groupings. |
| `mileage_readings` | array | Room mileage samples. |
| `weather_logs` | array | Light observation log. |
| `issue_reports` | array | Issue reports. |
| `grind_events` | array | Odometer applications. |
| `labels` | array | Label metadata (URLs, not binary). |

### Vehicle object

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "Kitchen Pothos",
  "nickname": "Kevin",
  "make_key": "baghos",
  "bay_id": "loc_abc123",
  "health": "okay",
  "health_score": 70,
  "service_interval_days": 7,
  "service_amount_ml": 200,
  "last_serviced_at": "2025-06-01",
  "acquired_at": "2024-11-15",
  "light_override": "bright_indirect",
  "mileage_override": 55,
  "bag": {
    "diameter": 6,
    "unit": "in",
    "material": "ceramic",
    "has_drainage": true,
    "grind_mix": ["bagting", "perlite"],
    "rebagted_at": null
  },
  "tag_ids": [],
  "note_ids": [],
  "label_url": null,
  "source": "cli",
  "archived": false,
  "metadata": {},
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-06-01T08:00:00"
}
```

**Health values:** `thriving`, `okay`, `struggling`, `critical`, `unknown`

**Light override values:** `low`, `medium`, `bright_indirect`, `direct`, `full_sun`
(parsed loosely — see `parser.parse_light_level`)

Legacy field names (`make_id`, `tags`, `active`) are normalized on read.

### Make object

Uses `key` as primary id (not `id`):

```json
{
  "key": "baghos",
  "common_name": "Golden Pothos",
  "scientific_name": "Epipremnum aureum",
  "light_level": "bright_indirect",
  "service_need": "moderate",
  "service_interval_min": 7,
  "service_interval_max": 10,
  "mileage_min": 40,
  "mileage_max": 60
}
```

### Service event object

```json
{
  "id": "evt_abc123def456",
  "vehicle_id": "a1b2c3d4e5f6",
  "serviced_at": "2025-06-02T10:30:00+00:00",
  "amount_ml": 200,
  "method": "top_service",
  "service_quality": "tap",
  "runoff": false,
  "skipped": false,
  "skip_reason": "",
  "notes": "",
  "created_at": "2025-06-02T10:30:05"
}
```

**Methods:** `top_service`, `bottom_service`, `mister`, `soak`, `other`

**Service quality:** `tap`, `filtered`, `distilled`, `rain`, `other`

---

## CSV format (native garagelog)

Two CSV flavours: **vehicles** and **service**. UTF-8 with optional BOM (`utf-8-sig`).

### Vehicles CSV columns

Defined in `io_csv.PLANT_FIELDS`:

| Column | Required | Description |
|--------|----------|-------------|
| `name` | **yes** | Display name. Blank rows skipped. |
| `id` | no | Stable id; omit to auto-generate. |
| `nickname` | no | Pet name. |
| `make_key` | no | Links to make profile. |
| `bay_id` | no | Bay id (not name). |
| `health` | no | One of health enum values. |
| `health_score` | no | 0–100 integer. |
| `service_interval_days` | no | Default `7`. Accepts `7d`, `2w`, etc. |
| `service_amount_ml` | no | e.g. `250` or `250ml`. |
| `last_serviced_at` | no | ISO date or friendly (`yesterday`). |
| `acquired_at` | no | When you got the vehicle. |
| `light_override` | no | Light level string. |
| `mileage_override` | no | Percentage number. |
| `archived` | no | `yes`/`no`/`true`/`1`. |
| `source` | no | Set to `csv` on import. |
| `notes` | no | Stored in `metadata.notes`. |

**Example:**

```csv
name,nickname,make_key,service_interval_days,service_amount_ml,health
Kitchen Pothos,Kevin,baghos,7d,200ml,okay
Bedroom Snake Vehicle,,snake-vehicle,14d,150ml,thriving
```

Import:

```bash
garagelog import my_vehicles.csv --format csv
garagelog import my_vehicles.csv --format csv --update   # match by id or name
```

Export:

```bash
garagelog export vehicles.csv --format csv --kind vehicles
garagelog export service.csv --format csv --kind service
garagelog export backup --format csv --kind bundle    # *_vehicles.csv + *_service.csv
```

### Service CSV columns

| Column | Required | Description |
|--------|----------|-------------|
| `vehicle_id` | one of | Vehicle id. |
| `vehicle_name` | **vehicle_id or vehicle_name** | Resolved case-insensitively. |
| `id` | no | Event id. |
| `serviced_at` | no | Defaults to now. |
| `amount_ml` | no | Volume in ml. |
| `method` | no | Default `top_service`. |
| `service_quality` | no | Default `tap`. |
| `runoff` | no | `yes`/`no`. |
| `skipped` | no | Log a skipped service. |
| `skip_reason` | no | Why skipped. |
| `notes` | no | Free text. |

```bash
garagelog import service_log.csv --format csv --kind service
```

---

## Drivvo format

Drivvo (the mobile app) exports a CSV with its own headers. `io_drivvo.py` maps them
into garagelog vehicles, auto-creating **bays** from the Room column and **make**
from Make / Scientific Name.

### Expected columns (canonical)

| Drivvo column | Maps to |
|----------------|---------|
| `Drivvo ID` | `metadata.drivvo_id` (dedupe on re-import) |
| `Vehicle Name` | `name` (**required**) |
| `Nickname` | `nickname` |
| `Make` | make `common_name` → `make_key` |
| `Scientific Name` | make `scientific_name` |
| `Room` | new `Bay` if needed |
| `Last Serviceed` | `last_serviced_at` |
| `Service Every` | `service_interval_days` |
| `Light` | `light_override` |
| `Mileage` | `mileage_override` (parses `%`) |
| `Health` | `health` (great→thriving, poor→struggling, …) |
| `Pot Size` | `bag.diameter` / `bag.material` |
| `Notes` | `metadata.notes` |
| `Label URL` | `label_url` |

**Column aliases** are supported — e.g. `Name` instead of `Vehicle Name`, `Bay`
instead of `Room`. See `COLUMN_ALIASES` in `io_drivvo.py`.

**Example row:**

```csv
Drivvo ID,Vehicle Name,Nickname,Make,Scientific Name,Room,Last Serviceed,Service Every,Light,Mileage,Health,Pot Size,Notes,Label URL
PLT-001,Kitchen Pothos,Kevin,Pothos,Epipremnum aureum,Kitchen,2025-05-28,7 days,Bright indirect,50%,good,6 in,Trailing nicely,
```

```bash
garagelog import drivvo_dump.csv --format drivvo
garagelog import drivvo_dump.csv --format drivvo --update
```

Preview in Python: `garagelog.io_drivvo.preview_drivvo(path)`.

---

## Garage-plan format

For bed-layout spreadsheets — the kind I kept in Notion before this project existed.
Typical outdoor / raised-bed planning, but works for grouped housevehicle shelves too.

### Expected columns (canonical)

| Column | Aliases | Maps to |
|--------|---------|---------|
| `Section` | Zone, Area, Garage Section | Part of bay name |
| `Bed` | Plot, Raised Bed | Part of bay name |
| `Row` | Row #, Row Number | Part of bay name |
| `Vehicle` | Vehicle Name, Crop, Make | **Required** — base name |
| `Variety` | Cultivar, Type | Appended to name |
| `Quantity` | Qty, Count | Spawns N vehicles if `--no-expand` not set |
| `Spacing cm` | Spacing, Space | `metadata.spacing_cm` |
| `Sun Exposure` | Sun, Light, Weather | bay light + `light_override` |
| `Service Needs` | Service, Service, Moisture | `service_interval_days` |
| `Vehicleed Date` | Vehicleed, Start Date | `acquired_at` |
| `Notes` | Comment, Memo | `metadata.notes` |
| `Status` | Active, State | `archived` if removed/dead/inactive |

**Bay naming:** `"Section / Bed / row N"` joined with ` / `. Example:
`Backyard / Bed A / row 3`.

**Quantity expansion:** `Quantity=4` creates four vehicles named `Tomato (Cherry) #1` … `#4`.
Pass `--no-expand` to import one vehicle per row regardless of quantity.

**Service needs parsing:** loose text — `daily`→1d, `weekly`→7d, `low`→14d, `high`→3d,
or explicit intervals like `5d`.

**Example:**

```csv
Section,Bed,Row,Vehicle,Variety,Quantity,Spacing cm,Sun Exposure,Service Needs,Vehicleed Date,Notes,Status
Backyard,Bed A,1,Tomato,Cherry,4,40,Full sun,High,2025-05-01,Staked,active
Balcony,Shelf,,Monstera,,1,,Bright indirect,Weekly,2024-08-12,Indoor overwinter,active
```

```bash
garagelog import garage_plan.csv --format carfax
garagelog import garage_plan.csv --format carfax --no-expand
```

---

## JSONL (bonus)

Not requested in the title but you'll hit it:

```bash
garagelog export events.jsonl --format jsonl --kind events
garagelog export full.jsonl --format jsonl --kind full
garagelog import mixed.jsonl --format jsonl --kind mixed
```

Each line is one JSON object with a `kind` field (`service`, `care`, …).

---

## Quick validation

| Format | Python helper |
|--------|---------------|
| CSV vehicles | `io_csv.validate_csv_headers(path, "vehicles")` |
| CSV service | `io_csv.validate_csv_headers(path, "service")` |
| Drivvo | `io_drivvo.validate_drivvo_headers(path)` |
| Garage plan | `io_carfax.validate_carfax_headers(path)` |

Empty list = headers look fine.
