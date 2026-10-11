from datetime import date
from typing import Dict

from nyc_health.models.appointment import AppointmentStatus
from nyc_health.models.billing import InvoiceStatus
from nyc_health.repositories.appointment_repo import AppointmentRepository
from nyc_health.repositories.billing_repo import InvoiceRepository
from nyc_health.services.bed_service import BedService


class ReportingService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        invoices: InvoiceRepository,
        beds: BedService,
    ) -> None:
        self._appointments = appointments
        self._invoices = invoices
        self._beds = beds

    def daily_appointment_summary(self, day: date) -> Dict[str, int]:
        summary = {status.value: 0 for status in AppointmentStatus}
        for appointment in self._appointments.on_day(day):
            summary[appointment.status.value] += 1
        summary["total"] = sum(summary.values())
        return summary

    def revenue_summary(self) -> Dict[str, int]:
        collected = billed_to_patients = billed_to_insurers = 0
        for invoice in self._invoices.list_all():
            if invoice.status in (InvoiceStatus.FINALIZED, InvoiceStatus.PAID):
                billed_to_patients += invoice.patient_owes_cents
                billed_to_insurers += invoice.insurer_pays_cents
                collected += invoice.paid_cents
        return {
            "billed_to_patients_cents": billed_to_patients,
            "billed_to_insurers_cents": billed_to_insurers,
            "collected_cents": collected,
            "outstanding_cents": billed_to_patients - collected,
        }

    def occupancy_percentages(self, hospital_id: str) -> Dict[str, float]:
        report = {}
        for ward, (occupied, total) in self._beds.occupancy(hospital_id).items():
            report[ward.value] = round(100 * occupied / total, 1) if total else 0.0
        return report
