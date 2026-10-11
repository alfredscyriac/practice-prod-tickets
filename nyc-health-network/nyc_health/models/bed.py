from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class WardType(Enum):
    GENERAL = "general"
    ICU = "icu"
    MATERNITY = "maternity"
    ISOLATION = "isolation"


@dataclass
class Bed:
    id: str
    hospital_id: str
    ward: WardType
    label: str
    occupied_by: Optional[str] = None  # admission id

    @property
    def is_free(self) -> bool:
        return self.occupied_by is None


@dataclass
class Admission:
    id: str
    patient_id: str
    hospital_id: str
    bed_id: str
    admitted_at: datetime
    reason: str = ""
    discharged_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.discharged_at is None

    def length_of_stay_hours(self, now: datetime) -> float:
        end = self.discharged_at or now
        return round((end - self.admitted_at).total_seconds() / 3600, 2)
