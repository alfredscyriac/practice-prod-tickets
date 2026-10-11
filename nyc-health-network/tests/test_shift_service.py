import pytest

from nyc_health.exceptions import NotFoundError, SchedulingConflictError, ValidationError
from tests.conftest import at


def test_assign_shift_rejects_overlap(container, nurse):
    container.shifts.assign_shift(nurse.id, at(8), at(16))
    with pytest.raises(SchedulingConflictError):
        container.shifts.assign_shift(nurse.id, at(15), at(20))


def test_back_to_back_shifts_are_allowed(container, nurse):
    container.shifts.assign_shift(nurse.id, at(8), at(16))
    container.shifts.assign_shift(nurse.id, at(16), at(20))
    assert len(container.shifts.shifts_for(nurse.id)) == 2


def test_shift_must_end_after_start(container, nurse):
    with pytest.raises(ValidationError):
        container.shifts.assign_shift(nurse.id, at(10), at(10))


def test_shift_length_is_capped(container, nurse):
    with pytest.raises(ValidationError):
        container.shifts.assign_shift(nurse.id, at(6), at(20))


def test_unknown_staff_rejected(container):
    with pytest.raises(NotFoundError):
        container.shifts.assign_shift("STF-404", at(8), at(12))


def test_is_on_duty_requires_full_coverage(container, nurse):
    container.shifts.assign_shift(nurse.id, at(8), at(12))
    assert container.shifts.is_on_duty(nurse.id, at(9), at(10))
    assert not container.shifts.is_on_duty(nurse.id, at(11, 30), at(12, 30))


def test_on_duty_now(container, nurse, doctor):
    container.shifts.assign_shift(nurse.id, at(8), at(12))
    assert container.shifts.on_duty_now(at(9)) == sorted([nurse.id, doctor.id])
    assert container.shifts.on_duty_now(at(13)) == [doctor.id]
