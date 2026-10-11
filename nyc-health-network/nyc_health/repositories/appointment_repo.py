from datetime import date
from typing import List

from nyc_health.models.appointment import Appointment, AppointmentStatus
from nyc_health.repositories.base import InMemoryRepository


class AppointmentRepository(InMemoryRepository[Appointment]):
    entity_name = "appointment"
    id_prefix = "APT"

    def active_for_doctor_on_day(self, doctor_id: str, day: date) -> List[Appointment]:
        return sorted(
            self.find(lambda a: a.doctor_id == doctor_id and a.is_active and a.start.date() == day),
            key=lambda a: a.start,
        )

    def active_for_patient_on_day(self, patient_id: str, day: date) -> List[Appointment]:
        return sorted(
            self.find(lambda a: a.patient_id == patient_id and a.is_active and a.start.date() == day),
            key=lambda a: a.start,
        )

    def for_patient(self, patient_id: str) -> List[Appointment]:
        return sorted(self.find(lambda a: a.patient_id == patient_id), key=lambda a: a.start)

    def by_status(self, status: AppointmentStatus) -> List[Appointment]:
        return self.find(lambda a: a.status is status)

    def on_day(self, day: date) -> List[Appointment]:
        return sorted(self.find(lambda a: a.start.date() == day), key=lambda a: a.start)
