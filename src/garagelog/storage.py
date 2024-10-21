"""JSON persistence layer for garage data.

Author: Marwan Helmy
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .errors import NotFoundError, StorageError, ValidationError
from .bay import Bay
from .vehicle import Vehicle
from .make import MakeProfile

SCHEMA_VERSION = 2

DEFAULT_CELLAR: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "vehicles": [],
    "make": [],
    "bays": [],
    "service_events": [],
    "inspection_logs": [],
    "tags": [],
    "notes": [],
    "audit": [],
    "plugins": [],
    "recurring": [],
    "collections": [],
    "mileage_readings": [],
    "weather_logs": [],
    "issue_reports": [],
    "grind_events": [],
    "labels": [],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}{raw}" if prefix else raw


def _normalize_vehicle_row(row: dict) -> dict:
    """Bridge legacy garage.json field names."""
    out = dict(row)
    if "make_key" not in out and out.get("make_id"):
        out["make_key"] = out["make_id"]
    if "tag_ids" not in out and out.get("tags"):
        out["tag_ids"] = list(out["tags"])
    if "archived" not in out and "active" in out:
        out["archived"] = not bool(out.get("active", True))
    return out


def _vehicle_payload(data: Vehicle | dict) -> dict:
    if isinstance(data, Vehicle):
        return data.to_dict()
    return _normalize_vehicle_row(dict(data))


def _normalize_make_row(row: dict) -> dict:
    out = dict(row)
    if "key" not in out and out.get("id"):
        out["key"] = out["id"]
    return out


def _make_payload(data: MakeProfile | dict) -> dict:
    if isinstance(data, MakeProfile):
        return data.to_dict()
    row = _normalize_make_row(dict(data))
    return row


class JsonStorage:
    """Thread-safe JSON file store with atomic writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = deepcopy(DEFAULT_CELLAR)
        if self.path.exists():
            self.load()
        else:
            self._ensure_parent()
            self.save()

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        with self._lock:
            try:
                text = self.path.read_text(encoding="utf-8")
                payload = json.loads(text)
            except (OSError, json.JSONDecodeError) as exc:
                raise StorageError(f"failed to load {self.path}: {exc}") from exc
            if not isinstance(payload, dict):
                raise StorageError("garage root must be an object")
            self._data = self._merge_defaults(payload)
            return deepcopy(self._data)

    def save(self) -> None:
        with self._lock:
            self._atomic_write(self._data)

    def _merge_defaults(self, payload: dict) -> dict:
        merged = deepcopy(DEFAULT_CELLAR)
        merged.update(payload)
        for key in DEFAULT_CELLAR:
            if key not in payload:
                merged[key] = deepcopy(DEFAULT_CELLAR[key])
        return merged

    def _atomic_write(self, data: dict) -> None:
        self._ensure_parent()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise StorageError(f"failed to save {self.path}: {exc}") from exc

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def replace_all(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._data = self._merge_defaults(data)
            self._atomic_write(self._data)

    # --- generic list CRUD ---

    def _list(self, bucket: str) -> list[dict]:
        items = self._data.get(bucket, [])
        if not isinstance(items, list):
            raise StorageError(f"bucket {bucket!r} is corrupt")
        return items

    def _find_index(self, bucket: str, item_id: str, id_field: str = "id") -> int:
        for idx, row in enumerate(self._list(bucket)):
            if row.get(id_field) == item_id:
                return idx
        raise NotFoundError(bucket, item_id)

    def _create(self, bucket: str, record: dict, id_field: str = "id") -> dict:
        with self._lock:
            if not record.get(id_field):
                record[id_field] = _new_id()
            if any(r.get(id_field) == record[id_field] for r in self._list(bucket)):
                raise ValidationError(f"duplicate {id_field} in {bucket}")
            record.setdefault("created_at", _utc_now())
            record.setdefault("updated_at", record["created_at"])
            self._list(bucket).append(record)
            self._atomic_write(self._data)
            return deepcopy(record)

    def _read(self, bucket: str, item_id: str, id_field: str = "id") -> dict:
        idx = self._find_index(bucket, item_id, id_field)
        return deepcopy(self._list(bucket)[idx])

    def _update(self, bucket: str, item_id: str, patch: dict, id_field: str = "id") -> dict:
        with self._lock:
            idx = self._find_index(bucket, item_id, id_field)
            row = self._list(bucket)[idx]
            for k, v in patch.items():
                if k == id_field:
                    continue
                row[k] = v
            row["updated_at"] = _utc_now()
            self._atomic_write(self._data)
            return deepcopy(row)

    def _delete(self, bucket: str, item_id: str, id_field: str = "id") -> None:
        with self._lock:
            idx = self._find_index(bucket, item_id, id_field)
            del self._list(bucket)[idx]
            self._atomic_write(self._data)

    def _list_all(self, bucket: str) -> list[dict]:
        with self._lock:
            return deepcopy(self._list(bucket))

    # --- vehicles ---

    def list_vehicles(self, active_only: bool = False) -> list[Vehicle]:
        rows = self._list_all("vehicles")
        if active_only:
            rows = [r for r in rows if not r.get("archived", False)]
        return [Vehicle.from_dict(_normalize_vehicle_row(r)) for r in rows]

    def get_vehicle(self, vehicle_id: str) -> Vehicle:
        return Vehicle.from_dict(_normalize_vehicle_row(self._read("vehicles", vehicle_id)))

    def create_vehicle(self, vehicle: Vehicle | dict) -> Vehicle:
        return Vehicle.from_dict(self._create("vehicles", _vehicle_payload(vehicle)))

    def update_vehicle(self, vehicle_id: str, patch: dict) -> Vehicle:
        return Vehicle.from_dict(self._update("vehicles", vehicle_id, _normalize_vehicle_row(patch)))

    def delete_vehicle(self, vehicle_id: str) -> None:
        self._delete("vehicles", vehicle_id)

    # --- make ---

    def list_make(self) -> list[MakeProfile]:
        return [MakeProfile.from_dict(_normalize_make_row(r)) for r in self._list_all("make")]

    def get_make(self, make_id: str) -> MakeProfile:
        for row in self._list_all("make"):
            if row.get("key") == make_id or row.get("id") == make_id:
                return MakeProfile.from_dict(_normalize_make_row(row))
        raise NotFoundError("make", make_id)

    def create_make(self, make: MakeProfile | dict) -> MakeProfile:
        row = _make_payload(make)
        created = self._create("make", row, id_field="key")
        return MakeProfile.from_dict(_normalize_make_row(created))

    def update_make(self, make_id: str, patch: dict) -> MakeProfile:
        row = self._update("make", make_id, _normalize_make_row(patch), id_field="key")
        return MakeProfile.from_dict(_normalize_make_row(row))

    def delete_make(self, make_id: str) -> None:
        with self._lock:
            rows = self._list("make")
            for idx, row in enumerate(rows):
                if row.get("key") == make_id or row.get("id") == make_id:
                    del rows[idx]
                    self._atomic_write(self._data)
                    return
        raise NotFoundError("make", make_id)

    # --- bays ---

    def list_bays(self) -> list[Bay]:
        return [Bay.from_dict(r) for r in self._list_all("bays")]

    def get_bay(self, bay_id: str) -> Bay:
        return Bay.from_dict(self._read("bays", bay_id))

    def create_bay(self, bay: Bay | dict) -> Bay:
        data = bay.to_dict() if isinstance(bay, Bay) else dict(bay)
        return Bay.from_dict(self._create("bays", data))

    def update_bay(self, bay_id: str, patch: dict) -> Bay:
        return Bay.from_dict(self._update("bays", bay_id, patch))

    def delete_bay(self, bay_id: str) -> None:
        self._delete("bays", bay_id)

    # --- service / care ---

    def list_service_events(self, vehicle_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("service_events")
        if vehicle_id:
            rows = [r for r in rows if r.get("vehicle_id") == vehicle_id]
        return rows

    def create_service_event(self, event: dict) -> dict:
        event.setdefault("serviced_at", _utc_now())
        created = self._create("service_events", event)
        # keep vehicle in sync - lazy but handy
        try:
            self.update_vehicle(created["vehicle_id"], {"last_serviced_at": created["serviced_at"]})
        except NotFoundError:
            pass
        return created

    def get_service_event(self, event_id: str) -> dict:
        return self._read("service_events", event_id)

    def update_service_event(self, event_id: str, patch: dict) -> dict:
        return self._update("service_events", event_id, patch)

    def delete_service_event(self, event_id: str) -> None:
        self._delete("service_events", event_id)

    def list_inspection_logs(self, vehicle_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("inspection_logs")
        if vehicle_id:
            rows = [r for r in rows if r.get("vehicle_id") == vehicle_id]
        return rows

    def create_inspection_log(self, log: dict) -> dict:
        log.setdefault("logged_at", _utc_now())
        return self._create("inspection_logs", log)

    def get_inspection_log(self, log_id: str) -> dict:
        return self._read("inspection_logs", log_id)

    def update_inspection_log(self, log_id: str, patch: dict) -> dict:
        return self._update("inspection_logs", log_id, patch)

    def delete_inspection_log(self, log_id: str) -> None:
        self._delete("inspection_logs", log_id)

    # --- tags / notes ---

    def list_tags(self) -> list[dict]:
        return self._list_all("tags")

    def create_tag(self, tag: dict) -> dict:
        tag.setdefault("name", tag.get("id", ""))
        return self._create("tags", tag)

    def update_tag(self, tag_id: str, patch: dict) -> dict:
        return self._update("tags", tag_id, patch)

    def delete_tag(self, tag_id: str) -> None:
        self._delete("tags", tag_id)

    def list_notes(self, vehicle_id: Optional[str] = None) -> list[dict]:
        rows = self._list_all("notes")
        if vehicle_id:
            rows = [r for r in rows if r.get("vehicle_id") == vehicle_id]
        return rows

    def create_note(self, note: dict) -> dict:
        note.setdefault("created_at", _utc_now())
        return self._create("notes", note)

    def update_note(self, note_id: str, patch: dict) -> dict:
        return self._update("notes", note_id, patch)

    def delete_note(self, note_id: str) -> None:
        self._delete("notes", note_id)

    # --- audit / plugins / recurring ---

    def list_audit(self) -> list[dict]:
        return self._list_all("audit")

    def append_audit(self, entry: dict) -> dict:
        entry.setdefault("timestamp", _utc_now())
        entry.setdefault("id", _new_id("aud_"))
        with self._lock:
            self._list("audit").append(entry)
            self._atomic_write(self._data)
            return deepcopy(entry)

    def list_plugins(self) -> list[dict]:
        return self._list_all("plugins")

    def upsert_plugin(self, plugin: dict) -> dict:
        pid = plugin.get("id")
        if not pid:
            return self._create("plugins", plugin)
        with self._lock:
            for idx, row in enumerate(self._list("plugins")):
                if row.get("id") == pid:
                    row.update(plugin)
                    row["updated_at"] = _utc_now()
                    self._atomic_write(self._data)
                    return deepcopy(row)
        return self._create("plugins", plugin)

    def delete_plugin(self, plugin_id: str) -> None:
        self._delete("plugins", plugin_id)

    def list_recurring(self) -> list[dict]:
        return self._list_all("recurring")

    def create_recurring(self, task: dict) -> dict:
        return self._create("recurring", task)

    def update_recurring(self, task_id: str, patch: dict) -> dict:
        return self._update("recurring", task_id, patch)

    def delete_recurring(self, task_id: str) -> None:
        self._delete("recurring", task_id)

    # --- extended buckets used by other modules ---

    def list_collections(self) -> list[dict]:
        return self._list_all("collections")

    def create_collection(self, coll: dict) -> dict:
        return self._create("collections", coll)

    def update_collection(self, coll_id: str, patch: dict) -> dict:
        return self._update("collections", coll_id, patch)

    def delete_collection(self, coll_id: str) -> None:
        self._delete("collections", coll_id)

    def mutate(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Run arbitrary in-lock mutation (used by migrations)."""
        with self._lock:
            fn(self._data)
            self._atomic_write(self._data)
