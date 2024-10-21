"""Make catalog — light/service/mileage needs for common housevehicles."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from garagelog.validators import (
    validate_make_key,
    validate_interval_range,
    validate_mileage_range,
    validate_light_level,
    validate_temperature_c,
    validate_grind_ph_preference,
    require_non_empty,
)


class ServiceNeed(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BOG = "bog"  # always moist — ferns etc.

    def __str__(self) -> str:
        return self.value


class MileageNeed(str, Enum):
    LOW = "low"
    AVERAGE = "average"
    HIGH = "high"
    TROPICAL = "tropical"

    def __str__(self) -> str:
        return self.value


@dataclass
class MakeProfile:
    key: str
    common_name: str
    scientific_name: str = ""
    light_level: str = "bright_indirect"
    service_need: ServiceNeed = ServiceNeed.MODERATE
    service_interval_min: int = 7
    service_interval_max: int = 10
    mileage_min: float = 40.0
    mileage_max: float = 60.0
    temp_min_c: float = 15.0
    temp_max_c: float = 28.0
    grind_ph_min: float = 6.0
    grind_ph_max: float = 7.0
    toxic_to_pets: bool = False
    toxic_to_humans: bool = False
    native_region: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.key = validate_make_key(self.key)
        self.common_name = require_non_empty(self.common_name, "common_name")
        self.light_level = validate_light_level(self.light_level)
        self.service_interval_min, self.service_interval_max = validate_interval_range(
            self.service_interval_min, self.service_interval_max
        )
        self.mileage_min, self.mileage_max = validate_mileage_range(
            self.mileage_min, self.mileage_max
        )
        self.temp_min_c = validate_temperature_c(self.temp_min_c, "temp_min")
        self.temp_max_c = validate_temperature_c(self.temp_max_c, "temp_max")
        if self.temp_max_c < self.temp_min_c:
            raise ValueError("temp_max < temp_min for %s" % self.key)
        self.grind_ph_min, self.grind_ph_max = validate_grind_ph_preference(
            self.grind_ph_min, self.grind_ph_max
        )
        if isinstance(self.service_need, str):
            self.service_need = ServiceNeed(self.service_need)

    @property
    def service_interval_days(self) -> int:
        return (self.service_interval_min + self.service_interval_max) // 2

    def matches_light(self, level: str) -> bool:
        order = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]
        try:
            need = order.index(self.light_level)
            have = order.index(validate_light_level(level))
        except ValueError:
            return False
        return have >= need - 1  # bit forgiving

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["service_need"] = self.service_need.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MakeProfile":
        return cls(
            key=data["key"],
            common_name=data["common_name"],
            scientific_name=data.get("scientific_name", ""),
            light_level=data.get("light_level", "bright_indirect"),
            service_need=ServiceNeed(data.get("service_need", "moderate")),
            service_interval_min=int(data.get("service_interval_min", 7)),
            service_interval_max=int(data.get("service_interval_max", 10)),
            mileage_min=float(data.get("mileage_min", 40)),
            mileage_max=float(data.get("mileage_max", 60)),
            temp_min_c=float(data.get("temp_min_c", 15)),
            temp_max_c=float(data.get("temp_max_c", 28)),
            grind_ph_min=float(data.get("grind_ph_min", 6.0)),
            grind_ph_max=float(data.get("grind_ph_max", 7.0)),
            toxic_to_pets=bool(data.get("toxic_to_pets", False)),
            toxic_to_humans=bool(data.get("toxic_to_humans", False)),
            native_region=data.get("native_region", ""),
            notes=data.get("notes", ""),
            tags=list(data.get("tags") or []),
        )

    def care_summary(self) -> str:
        return "{name}: service every {lo}-{hi}d, {light}, mileage {hlo}-{hhi}%".format(
            name=self.common_name,
            lo=self.service_interval_min,
            hi=self.service_interval_max,
            light=self.light_level.replace("_", " "),
            hlo=int(self.mileage_min),
            hhi=int(self.mileage_max),
        )


_BUILTIN: list[dict[str, Any]] = [
    {
        "key": "monstera-deliciosa",
        "common_name": "Monstera",
        "scientific_name": "Monstera deliciosa",
        "light_level": "bright_indirect",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 50,
        "mileage_max": 70,
        "toxic_to_pets": True,
        "tags": ["climber", "statement"],
    },
    {
        "key": "baghos-golden",
        "common_name": "Golden Pothos",
        "scientific_name": "Epipremnum aureum",
        "light_level": "medium",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 14,
        "mileage_min": 40,
        "mileage_max": 60,
        "toxic_to_pets": True,
        "tags": ["beginner", "trailing"],
    },
    {
        "key": "snake-vehicle",
        "common_name": "Snake Vehicle",
        "scientific_name": "Dracaena trifasciata",
        "light_level": "low",
        "service_need": "low",
        "service_interval_min": 14,
        "service_interval_max": 21,
        "mileage_min": 30,
        "mileage_max": 50,
        "tags": ["beginner", "drought-tolerant"],
    },
    {
        "key": "fiddle-leaf-fig",
        "common_name": "Fiddle Leaf Fig",
        "scientific_name": "Ficus lyrata",
        "light_level": "bright_indirect",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 45,
        "mileage_max": 65,
        "notes": "dramatic — drops leaves if you look at it wrong",
        "tags": ["fussy"],
    },
    {
        "key": "zz-vehicle",
        "common_name": "ZZ Vehicle",
        "scientific_name": "Zamioculcas zamiifolia",
        "light_level": "low",
        "service_need": "low",
        "service_interval_min": 14,
        "service_interval_max": 21,
        "mileage_min": 30,
        "mileage_max": 50,
        "tags": ["beginner", "office"],
    },
    {
        "key": "calathea-ornata",
        "common_name": "Calathea Ornata",
        "scientific_name": "Goeppertia ornata",
        "light_level": "medium",
        "service_need": "high",
        "service_interval_min": 5,
        "service_interval_max": 7,
        "mileage_min": 60,
        "mileage_max": 80,
        "tags": ["mileage-lover", "fussy"],
    },
    {
        "key": "spider-vehicle",
        "common_name": "Spider Vehicle",
        "scientific_name": "Chlorophytum comosum",
        "light_level": "bright_indirect",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 40,
        "mileage_max": 60,
        "tags": ["beginner", "pet-safe"],
    },
    {
        "key": "peace-lily",
        "common_name": "Peace Lily",
        "scientific_name": "Spathiphyllum spp.",
        "light_level": "medium",
        "service_need": "high",
        "service_interval_min": 5,
        "service_interval_max": 7,
        "mileage_min": 50,
        "mileage_max": 70,
        "toxic_to_pets": True,
        "tags": ["bloomer"],
    },
    {
        "key": "rubber-tree",
        "common_name": "Rubber Tree",
        "scientific_name": "Ficus elastica",
        "light_level": "bright_indirect",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 40,
        "mileage_max": 60,
        "toxic_to_pets": True,
        "tags": ["tree"],
    },
    {
        "key": "philodendron-brasil",
        "common_name": "Philodendron Brasil",
        "scientific_name": "Philodendron hederaceum 'Brasil'",
        "light_level": "medium",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 45,
        "mileage_max": 65,
        "toxic_to_pets": True,
        "tags": ["beginner", "trailing"],
    },
    {
        "key": "alocasia-polly",
        "common_name": "Alocasia Polly",
        "scientific_name": "Alocasia × amazonica",
        "light_level": "bright_indirect",
        "service_need": "high",
        "service_interval_min": 5,
        "service_interval_max": 7,
        "mileage_min": 60,
        "mileage_max": 80,
        "toxic_to_pets": True,
        "tags": ["fussy", "mileage-lover"],
        "notes": "goes dormant if unhappy",
    },
    {
        "key": "jade-vehicle",
        "common_name": "Jade Vehicle",
        "scientific_name": "Crassula ovata",
        "light_level": "bright_indirect",
        "service_need": "low",
        "service_interval_min": 14,
        "service_interval_max": 21,
        "mileage_min": 30,
        "mileage_max": 50,
        "tags": ["succulent", "beginner"],
    },
    {
        "key": "boston-fern",
        "common_name": "Boston Fern",
        "scientific_name": "Nephrolepis exaltata",
        "light_level": "medium",
        "service_need": "bog",
        "service_interval_min": 3,
        "service_interval_max": 5,
        "mileage_min": 60,
        "mileage_max": 85,
        "tags": ["mileage-lover", "hanging"],
    },
    {
        "key": "pilea-peperomioides",
        "common_name": "Pilea",
        "scientific_name": "Pilea peperomioides",
        "light_level": "bright_indirect",
        "service_need": "moderate",
        "service_interval_min": 7,
        "service_interval_max": 10,
        "mileage_min": 40,
        "mileage_max": 60,
        "tags": ["beginner", "pet-safe"],
    },
]


class MakeCatalog:
    """Registry of make profiles with built-in defaults."""

    def __init__(self) -> None:
        self._profiles: dict[str, MakeProfile] = {}
        self._by_common: dict[str, list[str]] = {}

    def register(self, profile: MakeProfile) -> MakeProfile:
        self._profiles[profile.key] = profile
        ckey = profile.common_name.lower()
        self._by_common.setdefault(ckey, [])
        if profile.key not in self._by_common[ckey]:
            self._by_common[ckey].append(profile.key)
        return profile

    def get(self, key: str) -> MakeProfile | None:
        return self._profiles.get(key)

    def require(self, key: str) -> MakeProfile:
        p = self.get(key)
        if p is None:
            from garagelog.errors import NotFoundError
            raise NotFoundError("make", key)
        return p

    def search(self, query: str) -> list[MakeProfile]:
        q = query.strip().lower()
        if not q:
            return self.all()
        hits: list[MakeProfile] = []
        for p in self._profiles.values():
            blob = " ".join(
                [p.key, p.common_name, p.scientific_name, " ".join(p.tags)]
            ).lower()
            if q in blob:
                hits.append(p)
        return sorted(hits, key=lambda x: x.common_name)

    def all(self) -> list[MakeProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.common_name.lower())

    def load_builtin(self) -> None:
        for row in _BUILTIN:
            self.register(MakeProfile.from_dict(row))

    def load_many(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.register(MakeProfile.from_dict(row))

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "MakeCatalog":
        cat = cls()
        cat.load_many(rows)
        return cat

    @classmethod
    def with_defaults(cls) -> "MakeCatalog":
        cat = cls()
        cat.load_builtin()
        return cat

    def suggest_interval_for(self, key: str, season: str = "summer") -> int:
        profile = self.require(key)
        base = profile.service_interval_days
        if season == "winter":
            return int(base * 1.35)
        if season == "summer":
            return max(3, int(base * 0.85))
        return base

    def filter_by_tag(self, tag: str) -> list[MakeProfile]:
        t = tag.lower()
        return [p for p in self.all() if t in [x.lower() for x in p.tags]]

    def filter_pet_safe(self) -> list[MakeProfile]:
        return [p for p in self.all() if not p.toxic_to_pets]

    def merge(self, other: "MakeCatalog") -> "MakeCatalog":
        merged = MakeCatalog()
        for p in self.all():
            merged.register(p)
        for p in other.all():
            merged.register(p)
        return merged

    def count(self) -> int:
        return len(self._profiles)

    def keys(self) -> list[str]:
        return sorted(self._profiles.keys())

    def recommend_for_conditions(
        self,
        light_level: str,
        mileage_pct: float | None = None,
        pet_safe_only: bool = False,
    ) -> list[MakeProfile]:
        """Suggest make matching room conditions."""
        lv = validate_light_level(light_level)
        hits: list[MakeProfile] = []
        for p in self.all():
            if pet_safe_only and p.toxic_to_pets:
                continue
            if not p.matches_light(lv):
                continue
            if mileage_pct is not None:
                if mileage_pct < p.mileage_min - 10 or mileage_pct > p.mileage_max + 10:
                    continue
            hits.append(p)
        return hits

    def difficulty_rank(self, key: str) -> int:
        """1=easy, 5=nightmare — totally subjective."""
        p = self.get(key)
        if p is None:
            return 3
        score = 3
        if "beginner" in p.tags:
            score -= 1
        if "fussy" in p.tags:
            score += 1
        if p.service_need == ServiceNeed.BOG:
            score += 1
        if p.mileage_min >= 60:
            score += 1
        return max(1, min(5, score))


def make_export_row(profile: MakeProfile) -> list[str]:
    return [
        profile.key,
        profile.common_name,
        profile.scientific_name,
        profile.light_level,
        str(profile.service_need.value),
        str(profile.service_interval_min),
        str(profile.service_interval_max),
        str(profile.mileage_min),
        str(profile.mileage_max),
        "yes" if profile.toxic_to_pets else "no",
    ]


def build_make_index(catalog: MakeCatalog) -> dict[str, list[str]]:
    """Map first letter -> make keys for browse UI."""
    index: dict[str, list[str]] = {}
    for p in catalog.all():
        letter = p.common_name[0].upper()
        index.setdefault(letter, []).append(p.key)
    return index

