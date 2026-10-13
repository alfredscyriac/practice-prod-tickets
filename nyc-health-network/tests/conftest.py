from datetime import date, datetime

import pytest

from nyc_health.container import Container, build_container
from nyc_health.core.clock import FrozenClock
from nyc_health.models.patient import Borough
from nyc_health.models.staff import Role, Specialty, Staff

NOW = datetime(2026, 3, 2, 7, 0)          # Monday 07:00
BOOKING_DAY = date(2026, 3, 3)            # Tuesday


def at(hour: int, minute: int = 0, day: date = BOOKING_DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def container(clock) -> Container:
    return build_container(clock)


@pytest.fixture
def doctor(container) -> Staff:
    doc = Staff(container.staff_repo.next_id(), "Dr. Priya Raman", Role.DOCTOR, "H-BELLEVUE", Specialty.CARDIOLOGY)
    container.staff_repo.add(doc)
    container.shifts.assign_shift(doc.id, at(8), at(18))
    return doc


@pytest.fixture
def second_doctor(container) -> Staff:
    doc = Staff(container.staff_repo.next_id(), "Dr. Marcus Allen", Role.DOCTOR, "H-BELLEVUE", Specialty.GENERAL)
    container.staff_repo.add(doc)
    container.shifts.assign_shift(doc.id, at(8), at(18))
    return doc


@pytest.fixture
def nurse(container) -> Staff:
    nurse = Staff(container.staff_repo.next_id(), "Nia Brooks", Role.NURSE, "H-BELLEVUE")
    container.staff_repo.add(nurse)
    return nurse


@pytest.fixture
def patient(container):
    return container.patients.register(
        "Maria", "Gonzalez", date(1985, 4, 12), "(718) 555-0142", Borough.QUEENS, "maria@example.com"
    )


@pytest.fixture
def other_patient(container):
    return container.patients.register("Devon", "Carter", date(1992, 11, 3), "212-555-0188", Borough.MANHATTAN)


@pytest.fixture
def insured_patient(container, patient):
    container.patients.attach_insurance(
        patient.id, "EmblemHealth Gold", "EMB-1029384", date(2026, 12, 31),
        copay_cents=3_000, deductible_cents=150_000, coverage_pct=80,
    )
    return container.patients.get(patient.id)  # reload: repositories return copies
