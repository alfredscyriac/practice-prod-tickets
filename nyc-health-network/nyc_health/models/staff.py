from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from nyc_health.utils.time_utils import minutes_between


class Role(Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class Specialty(Enum):
    GENERAL = "general"
    CARDIOLOGY = "cardiology"
    PEDIATRICS = "pediatrics"
    ORTHOPEDICS = "orthopedics"
    EMERGENCY = "emergency"


@dataclass
class Staff:
    id: str
    name: str
    role: Role
    hospital_id: str
    specialty: Optional[Specialty] = None

    @property
    def is_clinician(self) -> bool:
        return self.role in (Role.DOCTOR, Role.NURSE)


@dataclass
class Shift:
    id: str
    staff_id: str
    start: datetime
    end: datetime

    @property
    def duration_minutes(self) -> int:
        return minutes_between(self.start, self.end)

    def covers(self, start: datetime, end: datetime) -> bool:
        return self.start <= start and end <= self.end
