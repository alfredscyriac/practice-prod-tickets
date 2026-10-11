import pytest

from nyc_health.exceptions import BillingError, ValidationError
from nyc_health.models.billing import InvoiceStatus
from tests.conftest import at


def completed_appointment(container, doctor, patient, hour=9, procedure="CONSULT"):
    appt = container.scheduling.book(patient.id, doctor.id, at(hour), 30, procedure)
    container.scheduling.check_in(appt.id)
    container.scheduling.complete(appt.id)
    return appt


def test_uninsured_patient_owes_full_amount(container, doctor, patient):
    appt = completed_appointment(container, doctor, patient)
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_appointment_charge(invoice.id, appt.id)
    finalized = container.billing.finalize_invoice(invoice.id)
    assert finalized.status is InvoiceStatus.FINALIZED
    assert finalized.patient_owes_cents == 25_000
    assert finalized.insurer_pays_cents == 0


def test_insured_patient_first_invoice_goes_to_deductible(container, doctor, insured_patient):
    appt = completed_appointment(container, doctor, insured_patient)
    invoice = container.billing.create_invoice(insured_patient.id)
    container.billing.add_appointment_charge(invoice.id, appt.id)
    finalized = container.billing.finalize_invoice(invoice.id)
    assert finalized.deductible_applied_cents == 25_000
    assert finalized.patient_owes_cents == 25_000


def test_only_completed_appointments_billable(container, doctor, patient):
    appt = container.scheduling.book(patient.id, doctor.id, at(9))
    invoice = container.billing.create_invoice(patient.id)
    with pytest.raises(BillingError):
        container.billing.add_appointment_charge(invoice.id, appt.id)


def test_appointment_cannot_be_billed_twice(container, doctor, patient):
    appt = completed_appointment(container, doctor, patient)
    first = container.billing.create_invoice(patient.id)
    container.billing.add_appointment_charge(first.id, appt.id)
    second = container.billing.create_invoice(patient.id)
    with pytest.raises(BillingError):
        container.billing.add_appointment_charge(second.id, appt.id)


def test_cannot_bill_other_patients_appointment(container, doctor, patient, other_patient):
    appt = completed_appointment(container, doctor, patient)
    invoice = container.billing.create_invoice(other_patient.id)
    with pytest.raises(BillingError):
        container.billing.add_appointment_charge(invoice.id, appt.id)


def test_cannot_finalize_empty_invoice(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    with pytest.raises(BillingError):
        container.billing.finalize_invoice(invoice.id)


def test_finalized_invoice_is_immutable(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Wheelchair rental", 4_000)
    container.billing.finalize_invoice(invoice.id)
    with pytest.raises(BillingError):
        container.billing.add_custom_item(invoice.id, "Extra", 100)


def test_custom_item_must_be_positive(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    with pytest.raises(ValidationError):
        container.billing.add_custom_item(invoice.id, "Refund?", -100)


def test_payments_reduce_balance_and_mark_paid(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Splint", 10_000)
    container.billing.finalize_invoice(invoice.id)
    partial = container.billing.record_payment(invoice.id, 4_000)
    assert partial.balance_cents == 6_000 and partial.status is InvoiceStatus.FINALIZED
    paid = container.billing.record_payment(invoice.id, 6_000)
    assert paid.status is InvoiceStatus.PAID


def test_overpayment_rejected(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Splint", 10_000)
    container.billing.finalize_invoice(invoice.id)
    with pytest.raises(BillingError):
        container.billing.record_payment(invoice.id, 10_001)


def test_payment_requires_finalized_invoice(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    with pytest.raises(BillingError):
        container.billing.record_payment(invoice.id, 100)


def test_void_draft_invoice_allows_rebilling(container, doctor, patient):
    appt = completed_appointment(container, doctor, patient)
    first = container.billing.create_invoice(patient.id)
    container.billing.add_appointment_charge(first.id, appt.id)
    container.billing.void_invoice(first.id)
    second = container.billing.create_invoice(patient.id)
    container.billing.add_appointment_charge(second.id, appt.id)


def test_cannot_void_paid_invoice(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Splint", 1_000)
    container.billing.finalize_invoice(invoice.id)
    container.billing.record_payment(invoice.id, 1_000)
    with pytest.raises(BillingError):
        container.billing.void_invoice(invoice.id)


def test_no_show_fee(container, clock, doctor, patient):
    appt = container.scheduling.book(patient.id, doctor.id, at(9))
    clock.set(at(10))
    container.scheduling.mark_no_show(appt.id)
    invoice = container.billing.charge_no_show_fee(appt.id)
    assert invoice.patient_owes_cents == 5_000
    assert container.billing.outstanding_for_patient(patient.id) == 5_000


def test_no_show_fee_requires_no_show(container, doctor, patient):
    appt = container.scheduling.book(patient.id, doctor.id, at(9))
    with pytest.raises(BillingError):
        container.billing.charge_no_show_fee(appt.id)
