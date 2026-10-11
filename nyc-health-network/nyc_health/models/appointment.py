from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from nyc_health.exceptions import ValidationError


class AppointmentStatus(Enum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


_ALLOWED_TRANSITIONS = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CHECKED_IN: {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}

ACTIVE_STATUSES = (AppointmentStatus.SCHEDULED, AppointmentStatus.CHECKED_IN)


@dataclass
class Appointment:
    id: str
    patient_id: str
    doctor_id: str
    hospital_id: str
    start: datetime
    duration_minutes: int
    procedure_code: str
    created_at: datetime
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    notes: str = ""
    history: list = field(default_factory=list)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def can_transition_to(self, new_status: AppointmentStatus) -> bool:
        return new_status in _ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, new_status: AppointmentStatus, at: datetime) -> None:
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"cannot move appointment {self.id} from {self.status.value} to {new_status.value}"
            )
        self.history.append((self.status, new_status, at))
        self.status = new_status
