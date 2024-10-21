"""Consecutive service streak tracking.

Author: Marwan Helmy
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .vehicle import parse_iso
from .seasons import SeasonCalendar, effective_service_interval
from .storage import JsonStorage


@dataclass
class StreakInfo:
    vehicle_id: str
    vehicle_name: str
    current_streak: int
    longest_streak: int
    last_serviced: Optional[datetime]
    on_schedule: bool


class StreakTracker:
    GRACE_DAYS = 1.5  # little slack before streak breaks

    def __init__(self, storage: JsonStorage, seasons: Optional[SeasonCalendar] = None):
        self.storage = storage
        self.seasons = seasons or SeasonCalendar()

    def _events_for_vehicle(self, vehicle_id: str) -> list[datetime]:
        events = []
        for row in self.storage.list_service_events(vehicle_id=vehicle_id):
            dt = parse_iso(row.get("serviced_at"))
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                events.append(dt)
        events.sort(reverse=True)
        return events

    def compute(self, vehicle_id: str) -> StreakInfo:
        vehicle = self.storage.get_vehicle(vehicle_id)
        events = self._events_for_vehicle(vehicle_id)
        if not events:
            return StreakInfo(
                vehicle_id=vehicle_id,
                vehicle_name=vehicle.name,
                current_streak=0,
                longest_streak=0,
                last_serviced=None,
                on_schedule=False,
            )

        interval = effective_service_interval(
            vehicle.service_interval_days,
            self.seasons.multiplier_for(events[0]),
        )
        max_gap = timedelta(days=interval + self.GRACE_DAYS)

        current = 1
        longest = 1
        run = 1
        for i in range(len(events) - 1):
            gap = events[i] - events[i + 1]
            if gap <= max_gap:
                run += 1
            else:
                longest = max(longest, run)
                run = 1
        longest = max(longest, run)

        # current streak = consecutive from most recent
        current = 1
        for i in range(len(events) - 1):
            gap = events[i] - events[i + 1]
            if gap <= max_gap:
                current += 1
            else:
                break

        now = datetime.now(timezone.utc)
        on_schedule = (now - events[0]) <= max_gap

        return StreakInfo(
            vehicle_id=vehicle_id,
            vehicle_name=vehicle.name,
            current_streak=current if on_schedule else 0,
            longest_streak=longest,
            last_serviced=events[0],
            on_schedule=on_schedule,
        )

    def leaderboard(self, limit: int = 10) -> list[StreakInfo]:
        rows = [self.compute(p.id) for p in self.storage.list_vehicles()]
        rows.sort(key=lambda s: (s.current_streak, s.longest_streak), reverse=True)
        return rows[:limit]

    def broken_streaks(self) -> list[StreakInfo]:
        return [
            s for s in (self.compute(p.id) for p in self.storage.list_vehicles())
            if not s.on_schedule and s.last_serviced is not None
        ]
