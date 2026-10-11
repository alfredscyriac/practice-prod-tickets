from nyc_health.api import handlers
from nyc_health.models.bed import WardType
from tests.conftest import at


def test_book_appointment_returns_201(container, doctor, patient):
    status, body = handlers.book_appointment(
        container, {"patient_id": patient.id, "doctor_id": doctor.id, "start": at(9).isoformat()}
    )
    assert status == 201
    assert body["status"] == "scheduled"
    assert body["end"] == at(9, 30).isoformat()


def test_conflict_maps_to_409(container, doctor, patient, other_patient):
    payload = {"patient_id": patient.id, "doctor_id": doctor.id, "start": at(9).isoformat()}
    handlers.book_appointment(container, payload)
    status, body = handlers.book_appointment(container, {**payload, "patient_id": other_patient.id})
    assert status == 409
    assert "already has an appointment" in body["error"]


def test_missing_field_maps_to_400(container):
    status, body = handlers.book_appointment(container, {"patient_id": "PAT-1"})
    assert status == 400
    assert "doctor_id" in body["error"]


def test_unknown_entity_maps_to_404(container, doctor):
    status, _ = handlers.book_appointment(
        container, {"patient_id": "PAT-404", "doctor_id": doctor.id, "start": at(9).isoformat()}
    )
    assert status == 404


def test_cancel_and_reschedule_roundtrip(container, doctor, patient):
    _, booked = handlers.book_appointment(
        container, {"patient_id": patient.id, "doctor_id": doctor.id, "start": at(9).isoformat()}
    )
    status, moved = handlers.reschedule_appointment(
        container, {"appointment_id": booked["id"], "start": at(11).isoformat()}
    )
    assert status == 200 and moved["start"] == at(11).isoformat()
    status, cancelled = handlers.cancel_appointment(container, {"appointment_id": booked["id"]})
    assert cancelled["status"] == "cancelled"


def test_list_available_slots(container, doctor):
    status, body = handlers.list_available_slots(
        container, {"doctor_id": doctor.id, "date": "2026-03-03", "duration_minutes": 60}
    )
    assert status == 200
    assert body["slots"][0] == at(8).isoformat()


def test_invoice_flow(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Crutches", 6_000)
    status, body = handlers.finalize_invoice(container, {"invoice_id": invoice.id})
    assert status == 200 and body["patient_owes_cents"] == 6_000
    status, body = handlers.pay_invoice(container, {"invoice_id": invoice.id, "amount_cents": 99_999})
    assert status == 402


def test_admit_and_discharge(container, patient):
    container.beds.add_bed("H-KINGS", WardType.GENERAL, "GEN-01")
    status, admission = handlers.admit_patient(
        container, {"patient_id": patient.id, "hospital_id": "H-KINGS", "ward": "general"}
    )
    assert status == 201
    status, discharged = handlers.discharge_patient(container, {"admission_id": admission["id"]})
    assert discharged["discharged_at"] is not None
    status, _ = handlers.admit_patient(
        container, {"patient_id": patient.id, "hospital_id": "H-KINGS", "ward": "icu"}
    )
    assert status == 409
