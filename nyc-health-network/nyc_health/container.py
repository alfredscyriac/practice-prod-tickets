"""Composition root: builds repositories and services and wires them together."""
from dataclasses import dataclass
from typing import Optional

from nyc_health.core.clock import Clock
from nyc_health.core.event_bus import EventBus
from nyc_health.repositories.appointment_repo import AppointmentRepository
from nyc_health.repositories.bed_repo import AdmissionRepository, BedRepository
from nyc_health.repositories.billing_repo import InvoiceRepository
from nyc_health.repositories.insurance_repo import PolicyRepository
from nyc_health.repositories.notification_repo import NotificationRepository
from nyc_health.repositories.patient_repo import PatientRepository
from nyc_health.repositories.staff_repo import ShiftRepository, StaffRepository
from nyc_health.services.bed_service import BedService
from nyc_health.services.billing_service import BillingService
from nyc_health.services.insurance_service import InsuranceService
from nyc_health.services.notification_service import NotificationService
from nyc_health.services.patient_service import PatientService
from nyc_health.services.reporting_service import ReportingService
from nyc_health.services.scheduling_service import SchedulingService
from nyc_health.services.shift_service import ShiftService
from nyc_health.utils.ids import IdGenerator


@dataclass
class Container:
    clock: Clock
    events: EventBus
    patients_repo: PatientRepository
    staff_repo: StaffRepository
    shifts_repo: ShiftRepository
    appointments_repo: AppointmentRepository
    beds_repo: BedRepository
    admissions_repo: AdmissionRepository
    invoices_repo: InvoiceRepository
    policies_repo: PolicyRepository
    notifications_repo: NotificationRepository
    patients: PatientService
    shifts: ShiftService
    scheduling: SchedulingService
    notifications: NotificationService
    insurance: InsuranceService
    billing: BillingService
    beds: BedService
    reporting: ReportingService


def build_container(clock: Optional[Clock] = None) -> Container:
    clock = clock or Clock()
    ids = IdGenerator()
    events = EventBus()

    patients_repo = PatientRepository(ids)
    staff_repo = StaffRepository(ids)
    shifts_repo = ShiftRepository(ids)
    appointments_repo = AppointmentRepository(ids)
    beds_repo = BedRepository(ids)
    admissions_repo = AdmissionRepository(ids)
    invoices_repo = InvoiceRepository(ids)
    policies_repo = PolicyRepository(ids)
    notifications_repo = NotificationRepository(ids)

    patients = PatientService(patients_repo, policies_repo, clock)
    shifts = ShiftService(shifts_repo, staff_repo)
    scheduling = SchedulingService(appointments_repo, patients_repo, staff_repo, shifts, events, clock)
    notifications = NotificationService(notifications_repo, patients_repo, events, clock)
    insurance = InsuranceService(policies_repo)
    billing = BillingService(invoices_repo, appointments_repo, patients_repo, insurance, clock)
    beds = BedService(beds_repo, admissions_repo, patients_repo, events, clock)
    reporting = ReportingService(appointments_repo, invoices_repo, beds)

    return Container(
        clock=clock, events=events, patients_repo=patients_repo, staff_repo=staff_repo,
        shifts_repo=shifts_repo, appointments_repo=appointments_repo, beds_repo=beds_repo,
        admissions_repo=admissions_repo, invoices_repo=invoices_repo, policies_repo=policies_repo,
        notifications_repo=notifications_repo, patients=patients, shifts=shifts,
        scheduling=scheduling, notifications=notifications, insurance=insurance,
        billing=billing, beds=beds, reporting=reporting,
    )
