"""Thin request handlers: parse a payload dict, call a service, return (status, body)."""
from datetime import datetime
from typing import Any, Callable, Dict, Tuple

from nyc_health.container import Container
from nyc_health.exceptions import (
    BillingError,
    CapacityError,
    HospitalError,
    NotFoundError,
    SchedulingConflictError,
    ValidationError,
)
from nyc_health.models.appointment import Appointment
from nyc_health.models.bed import Admission, WardType
from nyc_health.models.billing import Invoice

Response = Tuple[int, Dict[str, Any]]

_STATUS_FOR_ERROR = (
    (NotFoundError, 404),
    (ValidationError, 422),
    (SchedulingConflictError, 409),
    (CapacityError, 409),
    (BillingError, 402),
    (HospitalError, 400),
)


def handle_errors(func: Callable[..., Response]) -> Callable[..., Response]:
    def wrapper(container: Container, payload: Dict[str, Any]) -> Response:
        try:
            return func(container, payload)
        except HospitalError as exc:
            for error_type, status in _STATUS_FOR_ERROR:
                if isinstance(exc, error_type):
                    return status, {"error": str(exc)}
            return 400, {"error": str(exc)}
        except KeyError as exc:
            return 400, {"error": f"missing field {exc}"}

    wrapper.__name__ = func.__name__
    return wrapper


def serialize_appointment(appointment: Appointment) -> Dict[str, Any]:
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
        "hospital_id": appointment.hospital_id,
        "start": appointment.start.isoformat(),
        "end": appointment.end.isoformat(),
        "procedure_code": appointment.procedure_code,
        "status": appointment.status.value,
    }


def serialize_invoice(invoice: Invoice) -> Dict[str, Any]:
    return {
        "id": invoice.id,
        "patient_id": invoice.patient_id,
        "status": invoice.status.value,
        "subtotal_cents": invoice.subtotal_cents,
        "insurer_pays_cents": invoice.insurer_pays_cents,
        "patient_owes_cents": invoice.patient_owes_cents,
        "paid_cents": invoice.paid_cents,
        "balance_cents": invoice.balance_cents,
    }


def serialize_admission(admission: Admission) -> Dict[str, Any]:
    return {
        "id": admission.id,
        "patient_id": admission.patient_id,
        "hospital_id": admission.hospital_id,
        "bed_id": admission.bed_id,
        "admitted_at": admission.admitted_at.isoformat(),
        "discharged_at": admission.discharged_at.isoformat() if admission.discharged_at else None,
    }


@handle_errors
def book_appointment(container: Container, payload: Dict[str, Any]) -> Response:
    appointment = container.scheduling.book(
        patient_id=payload["patient_id"],
        doctor_id=payload["doctor_id"],
        start=datetime.fromisoformat(payload["start"]),
        duration_minutes=payload.get("duration_minutes", 30),
        procedure_code=payload.get("procedure_code", "CONSULT"),
    )
    return 201, serialize_appointment(appointment)


@handle_errors
def cancel_appointment(container: Container, payload: Dict[str, Any]) -> Response:
    appointment = container.scheduling.cancel(payload["appointment_id"], payload.get("reason", ""))
    return 200, serialize_appointment(appointment)


@handle_errors
def reschedule_appointment(container: Container, payload: Dict[str, Any]) -> Response:
    appointment = container.scheduling.reschedule(
        payload["appointment_id"],
        datetime.fromisoformat(payload["start"]),
        payload.get("duration_minutes"),
    )
    return 200, serialize_appointment(appointment)


@handle_errors
def list_available_slots(container: Container, payload: Dict[str, Any]) -> Response:
    day = datetime.fromisoformat(payload["date"]).date()
    slots = container.scheduling.available_slots(
        payload["doctor_id"], day, payload.get("duration_minutes", 30)
    )
    return 200, {"slots": [slot.isoformat() for slot in slots]}


@handle_errors
def finalize_invoice(container: Container, payload: Dict[str, Any]) -> Response:
    return 200, serialize_invoice(container.billing.finalize_invoice(payload["invoice_id"]))


@handle_errors
def pay_invoice(container: Container, payload: Dict[str, Any]) -> Response:
    invoice = container.billing.record_payment(payload["invoice_id"], payload["amount_cents"])
    return 200, serialize_invoice(invoice)


@handle_errors
def admit_patient(container: Container, payload: Dict[str, Any]) -> Response:
    admission = container.beds.admit(
        payload["patient_id"],
        payload["hospital_id"],
        WardType(payload["ward"]),
        payload.get("reason", ""),
    )
    return 201, serialize_admission(admission)


@handle_errors
def discharge_patient(container: Container, payload: Dict[str, Any]) -> Response:
    return 200, serialize_admission(container.beds.discharge(payload["admission_id"]))
