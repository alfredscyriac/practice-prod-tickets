"""Demo data: a handful of NYC Health + Hospitals style facilities, staff, beds and patients."""
from datetime import date, datetime
from typing import Dict, List

from nyc_health.container import Container
from nyc_health.models.bed import WardType
from nyc_health.models.hospital import Hospital
from nyc_health.models.patient import Borough
from nyc_health.models.staff import Role, Specialty, Staff

HOSPITALS: List[Hospital] = [
    Hospital("H-BELLEVUE", "Bellevue Hospital Center", Borough.MANHATTAN,
             {WardType.GENERAL: 4, WardType.ICU: 2, WardType.ISOLATION: 2}),
    Hospital("H-KINGS", "Kings County Hospital", Borough.BROOKLYN,
             {WardType.GENERAL: 3, WardType.MATERNITY: 2, WardType.ISOLATION: 1}),
    Hospital("H-ELMHURST", "Elmhurst Hospital", Borough.QUEENS,
             {WardType.GENERAL: 3, WardType.ICU: 1}),
    Hospital("H-LINCOLN", "Lincoln Medical Center", Borough.BRONX,
             {WardType.GENERAL: 3, WardType.ISOLATION: 1}),
]

_DOCTORS = [
    ("Dr. Priya Raman", "H-BELLEVUE", Specialty.CARDIOLOGY),
    ("Dr. Marcus Allen", "H-BELLEVUE", Specialty.GENERAL),
    ("Dr. Sofia Alvarez", "H-KINGS", Specialty.PEDIATRICS),
    ("Dr. Wei Chen", "H-ELMHURST", Specialty.ORTHOPEDICS),
    ("Dr. Jamal Brooks", "H-LINCOLN", Specialty.EMERGENCY),
]

_PATIENTS = [
    ("Maria", "Gonzalez", date(1985, 4, 12), "(718) 555-0142", Borough.QUEENS),
    ("Devon", "Carter", date(1992, 11, 3), "212-555-0188", Borough.MANHATTAN),
    ("Aisha", "Rahman", date(2016, 7, 21), "917.555.0107", Borough.BROOKLYN),
    ("Tomasz", "Kowalski", date(1958, 1, 30), "646 555 0163", Borough.BRONX),
]


def seed(container: Container, shift_day: date) -> Dict[str, list]:
    """Populate `container` and give every doctor a 08:00-18:00 shift on `shift_day`."""
    doctors, patients = [], []
    for name, hospital_id, specialty in _DOCTORS:
        doctor = Staff(container.staff_repo.next_id(), name, Role.DOCTOR, hospital_id, specialty)
        container.staff_repo.add(doctor)
        container.shifts.assign_shift(
            doctor.id,
            datetime(shift_day.year, shift_day.month, shift_day.day, 8),
            datetime(shift_day.year, shift_day.month, shift_day.day, 18),
        )
        doctors.append(doctor)

    for hospital in HOSPITALS:
        for ward, count in hospital.ward_targets.items():
            for number in range(1, count + 1):
                container.beds.add_bed(hospital.id, ward, f"{ward.value[:3].upper()}-{number:02d}")

    for first, last, dob, phone, borough in _PATIENTS:
        patients.append(container.patients.register(first, last, dob, phone, borough))

    return {"doctors": doctors, "patients": patients, "hospitals": HOSPITALS}
