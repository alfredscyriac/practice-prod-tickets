from datetime import date
from typing import List

from nyc_health.models.appointment import ACTIVE_STATUSES, Appointment, AppointmentStatus
from nyc_health.repositories.base import MongoRepository
from nyc_health.utils.time_utils import day_bounds

_ACTIVE_VALUES = [status.value for status in ACTIVE_STATUSES]


class AppointmentRepository(MongoRepository[Appointment]):
    entity_name = "appointment"
    id_prefix = "APT"
    collection_name = "appointments"
    model = Appointment
    indexes = [("doctor_id",), ("patient_id",)]

    def active_for_doctor_on_day(self, doctor_id: str, day: date) -> List[Appointment]:
        day_start, day_end = day_bounds(day)
        return self.find_where(
            {
                "doctor_id": doctor_id,
                "status": {"$in": _ACTIVE_VALUES},
                "start": {"$gte": day_start, "$lt": day_end},
            },
            sort=[("start", 1)],
        )

    def active_for_patient_on_day(self, patient_id: str, day: date) -> List[Appointment]:
        day_start, day_end = day_bounds(day)
        return self.find_where(
            {
                "patient_id": patient_id,
                "status": {"$in": _ACTIVE_VALUES},
                "start": {"$gte": day_start, "$lt": day_end},
            },
            sort=[("start", 1)],
        )

    def for_patient(self, patient_id: str) -> List[Appointment]:
        return self.find_where({"patient_id": patient_id}, sort=[("start", 1)])

    def by_status(self, status: AppointmentStatus) -> List[Appointment]:
        return self.find_where({"status": status.value})

    def on_day(self, day: date) -> List[Appointment]:
        day_start, day_end = day_bounds(day)
        return self.find_where({"start": {"$gte": day_start, "$lt": day_end}}, sort=[("start", 1)])
