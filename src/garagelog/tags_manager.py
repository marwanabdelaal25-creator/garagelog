"""Bulk tag operations across vehicles.

Author: Marwan Helmy
"""

from __future__ import annotations

from typing import Iterable, Optional

from .errors import NotFoundError, ValidationError
from .storage import JsonStorage


class TagsManager:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def ensure_tag(self, name: str, color: str = "") -> dict:
        name = name.strip().lower()
        if not name:
            raise ValidationError("tag name empty")
        for tag in self.storage.list_tags():
            if tag.get("name", "").lower() == name:
                return tag
        return self.storage.create_tag({"name": name, "color": color})

    def add_to_vehicle(self, vehicle_id: str, tag: str) -> dict:
        vehicle = self.storage.get_vehicle(vehicle_id)
        self.ensure_tag(tag)
        tags = list(vehicle.tag_ids)
        t = tag.strip().lower()
        if t not in tags:
            tags.append(t)
        return self.storage.update_vehicle(vehicle_id, {"tag_ids": tags}).to_dict()

    def remove_from_vehicle(self, vehicle_id: str, tag: str) -> dict:
        vehicle = self.storage.get_vehicle(vehicle_id)
        t = tag.strip().lower()
        tags = [x for x in vehicle.tag_ids if x != t]
        return self.storage.update_vehicle(vehicle_id, {"tag_ids": tags}).to_dict()

    def bulk_add(self, vehicle_ids: Iterable[str], tag: str) -> list[dict]:
        results = []
        for pid in vehicle_ids:
            try:
                results.append(self.add_to_vehicle(pid, tag))
            except NotFoundError:
                pass
        return results

    def bulk_remove(self, vehicle_ids: Iterable[str], tag: str) -> list[dict]:
        results = []
        for pid in vehicle_ids:
            try:
                results.append(self.remove_from_vehicle(pid, tag))
            except NotFoundError:
                pass
        return results

    def vehicles_with_tag(self, tag: str) -> list[dict]:
        t = tag.strip().lower()
        return [
            p.to_dict()
            for p in self.storage.list_vehicles(active_only=False)
            if t in [x.lower() for x in p.tag_ids]
        ]

    def rename_tag(self, old_name: str, new_name: str) -> int:
        old = old_name.strip().lower()
        new = new_name.strip().lower()
        if not new:
            raise ValidationError("new tag name empty")
        count = 0
        for vehicle in self.storage.list_vehicles(active_only=False):
            tags = [new if x.lower() == old else x for x in vehicle.tag_ids]
            if tags != vehicle.tag_ids:
                self.storage.update_vehicle(vehicle.id, {"tag_ids": tags})
                count += 1
        for tag in self.storage.list_tags():
            if tag.get("name", "").lower() == old:
                self.storage.update_tag(tag["id"], {"name": new})
        if count == 0 and old != new:
            self.ensure_tag(new)
        return count

    def unused_tags(self) -> list[str]:
        defined = {t.get("name", "").lower() for t in self.storage.list_tags()}
        used = set()
        for vehicle in self.storage.list_vehicles(active_only=False):
            used.update(x.lower() for x in vehicle.tag_ids)
        return sorted(defined - used)

    def tag_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for vehicle in self.storage.list_vehicles(active_only=False):
            for t in vehicle.tag_ids:
                key = t.lower()
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def merge_tags(self, source: str, target: str) -> int:
        src = source.strip().lower()
        tgt = target.strip().lower()
        self.ensure_tag(tgt)
        changed = 0
        for vehicle in self.storage.list_vehicles(active_only=False):
            tags = list(vehicle.tag_ids)
            if src not in [x.lower() for x in tags]:
                continue
            new_tags = []
            seen = set()
            for x in tags:
                val = tgt if x.lower() == src else x
                lk = val.lower()
                if lk not in seen:
                    new_tags.append(val)
                    seen.add(lk)
            self.storage.update_vehicle(vehicle.id, {"tag_ids": new_tags})
            changed += 1
        return changed
