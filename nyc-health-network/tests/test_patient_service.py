from datetime import date

import pytest

from nyc_health.exceptions import NotFoundError, ValidationError
from nyc_health.models.notification import NotificationChannel
from nyc_health.models.patient import Borough


def test_register_normalizes_contact_details(container):
    patient = container.patients.register(
        " Aisha ", "Rahman", date(2016, 7, 21), "917.555.0107", Borough.BROOKLYN, "Aisha@Example.com"
    )
    assert patient.first_name == "Aisha"
    assert patient.phone == "+19175550107"
    assert patient.email == "aisha@example.com"
    assert patient.id == "PAT-00001"


def test_register_rejects_duplicate_phone(container, patient):
    with pytest.raises(ValidationError):
        container.patients.register("Other", "Person", date(1990, 1, 1), "718-555-0142", Borough.QUEENS)


def test_get_unknown_patient_raises(container):
    with pytest.raises(NotFoundError):
        container.patients.get("PAT-99999")


def test_update_contact_validates_phone(container, patient):
    updated = container.patients.update_contact(patient.id, phone="212 555 0101")
    assert updated.phone == "+12125550101"
    with pytest.raises(ValidationError):
        container.patients.update_contact(patient.id, phone="123")


def test_email_preference_requires_email(container, other_patient):
    with pytest.raises(ValidationError):
        container.patients.update_contact(other_patient.id, preferred_channel=NotificationChannel.EMAIL)


def test_attach_insurance_links_policy(container, patient):
    policy = container.patients.attach_insurance(patient.id, "Fidelis Care", "FID-1", date(2027, 1, 1))
    assert container.patients.get(patient.id).insurance_policy_id == policy.id
    assert policy.deductible_met_cents == 0


def test_attach_insurance_rejects_expired_policy(container, patient):
    with pytest.raises(ValidationError):
        container.patients.attach_insurance(patient.id, "Old Plan", "OLD-1", date(2020, 1, 1))


def test_search_by_last_name_is_case_insensitive_and_sorted(container, patient, other_patient):
    results = container.patients.search("ar")
    assert [p.last_name for p in results] == ["Carter"]
    assert [p.last_name for p in container.patients.search("GON")] == ["Gonzalez"]


def test_age_calculation_respects_birthday(patient):
    assert patient.age_on(date(2026, 4, 11)) == 40
    assert patient.age_on(date(2026, 4, 12)) == 41
