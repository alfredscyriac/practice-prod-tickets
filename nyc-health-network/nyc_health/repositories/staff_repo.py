from datetime import datetime
from typing import List

from nyc_health.models.staff import Role, Shift, Specialty, Staff
from nyc_health.repositories.base import InMemoryRepository


class StaffRepository(InMemoryRepository[Staff]):
    entity_name = "staff member"
    id_prefix = "STF"

    def by_role(self, role: Role) -> List[Staff]:
        return self.find(lambda s: s.role is role)

    def doctors_by_specialty(self, specialty: Specialty, hospital_id: str = None) -> List[Staff]:
        return self.find(
            lambda s: s.role is Role.DOCTOR
            and s.specialty is specialty
            and (hospital_id is None or s.hospital_id == hospital_id)
        )


class ShiftRepository(InMemoryRepository[Shift]):
    entity_name = "shift"
    id_prefix = "SHF"

    def for_staff(self, staff_id: str) -> List[Shift]:
        return sorted(self.find(lambda s: s.staff_id == staff_id), key=lambda s: s.start)

    def on_day(self, day) -> List[Shift]:
        return self.find(lambda s: s.start.date() == day)

    def active_at(self, moment: datetime) -> List[Shift]:
        return self.find(lambda s: s.start <= moment < s.end)
