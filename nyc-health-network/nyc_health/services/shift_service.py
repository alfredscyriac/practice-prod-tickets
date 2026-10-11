from datetime import datetime, timedelta
from typing import List

from nyc_health import config
from nyc_health.exceptions import SchedulingConflictError, ValidationError
from nyc_health.models.staff import Shift
from nyc_health.repositories.staff_repo import ShiftRepository, StaffRepository
from nyc_health.utils.time_utils import intervals_overlap


class ShiftService:
    def __init__(self, shifts: ShiftRepository, staff: StaffRepository) -> None:
        self._shifts = shifts
        self._staff = staff

    def assign_shift(self, staff_id: str, start: datetime, end: datetime) -> Shift:
        self._staff.get(staff_id)
        if end <= start:
            raise ValidationError("shift must end after it starts")
        if end - start > timedelta(hours=config.MAX_SHIFT_HOURS):
            raise ValidationError(f"shifts are limited to {config.MAX_SHIFT_HOURS} hours")
        for existing in self._shifts.for_staff(staff_id):
            if intervals_overlap(existing.start, existing.end, start, end):
                raise SchedulingConflictError(
                    f"staff member {staff_id} already has a shift from {existing.start} to {existing.end}"
                )
        shift = Shift(id=self._shifts.next_id(), staff_id=staff_id, start=start, end=end)
        return self._shifts.add(shift)

    def is_on_duty(self, staff_id: str, start: datetime, end: datetime) -> bool:
        return any(shift.covers(start, end) for shift in self._shifts.for_staff(staff_id))

    def shifts_for(self, staff_id: str) -> List[Shift]:
        return self._shifts.for_staff(staff_id)

    def on_duty_now(self, moment: datetime) -> List[str]:
        return sorted({shift.staff_id for shift in self._shifts.active_at(moment)})

    def remove_shift(self, shift_id: str) -> None:
        self._shifts.delete(shift_id)
