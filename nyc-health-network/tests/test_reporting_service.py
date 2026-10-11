from nyc_health.models.bed import WardType
from tests.conftest import BOOKING_DAY, at


def test_daily_summary_counts_by_status(container, doctor, patient, other_patient):
    a = container.scheduling.book(patient.id, doctor.id, at(9))
    container.scheduling.book(other_patient.id, doctor.id, at(10))
    container.scheduling.cancel(a.id)
    summary = container.reporting.daily_appointment_summary(BOOKING_DAY)
    assert summary["cancelled"] == 1
    assert summary["scheduled"] == 1
    assert summary["total"] == 2


def test_revenue_summary(container, patient):
    invoice = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(invoice.id, "Cast", 20_000)
    container.billing.finalize_invoice(invoice.id)
    container.billing.record_payment(invoice.id, 5_000)
    summary = container.reporting.revenue_summary()
    assert summary["billed_to_patients_cents"] == 20_000
    assert summary["collected_cents"] == 5_000
    assert summary["outstanding_cents"] == 15_000


def test_revenue_summary_ignores_drafts_and_voids(container, patient):
    draft = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(draft.id, "Cast", 20_000)
    voided = container.billing.create_invoice(patient.id)
    container.billing.add_custom_item(voided.id, "Cast", 20_000)
    container.billing.void_invoice(voided.id)
    assert container.reporting.revenue_summary()["billed_to_patients_cents"] == 0


def test_occupancy_percentages(container, patient):
    container.beds.add_bed("H-BELLEVUE", WardType.ICU, "ICU-01")
    container.beds.add_bed("H-BELLEVUE", WardType.ICU, "ICU-02")
    container.beds.admit(patient.id, "H-BELLEVUE", WardType.ICU)
    assert container.reporting.occupancy_percentages("H-BELLEVUE") == {"icu": 50.0}
