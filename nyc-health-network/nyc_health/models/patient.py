from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from nyc_health.models.notification import NotificationChannel


class Borough(Enum):
    MANHATTAN = "manhattan"
    BROOKLYN = "brooklyn"
    QUEENS = "queens"
    BRONX = "bronx"
    STATEN_ISLAND = "staten_island"


@dataclass
class Patient:
    id: str
    first_name: str
    last_name: str
    date_of_birth: date
    phone: str
    borough: Borough
    email: Optional[str] = None
    insurance_policy_id: Optional[str] = None
    is_infectious: bool = False
    preferred_channel: NotificationChannel = NotificationChannel.SMS

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age_on(self, on: date) -> int:
        years = on.year - self.date_of_birth.year
        if (on.month, on.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years

    @property
    def has_insurance(self) -> bool:
        return self.insurance_policy_id is not None
