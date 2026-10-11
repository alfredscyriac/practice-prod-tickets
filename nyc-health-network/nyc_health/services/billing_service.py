from nyc_health import config
from nyc_health.core.clock import Clock
from nyc_health.exceptions import BillingError, ValidationError
from nyc_health.models.appointment import AppointmentStatus
from nyc_health.models.billing import Invoice, InvoiceStatus, LineItem
from nyc_health.repositories.appointment_repo import AppointmentRepository
from nyc_health.repositories.billing_repo import InvoiceRepository
from nyc_health.repositories.patient_repo import PatientRepository
from nyc_health.services.insurance_service import InsuranceService


class BillingService:
    def __init__(
        self,
        invoices: InvoiceRepository,
        appointments: AppointmentRepository,
        patients: PatientRepository,
        insurance: InsuranceService,
        clock: Clock,
    ) -> None:
        self._invoices = invoices
        self._appointments = appointments
        self._patients = patients
        self._insurance = insurance
        self._clock = clock

    def create_invoice(self, patient_id: str) -> Invoice:
        self._patients.get(patient_id)
        invoice = Invoice(id=self._invoices.next_id(), patient_id=patient_id, created_at=self._clock.now())
        return self._invoices.add(invoice)

    def add_appointment_charge(self, invoice_id: str, appointment_id: str) -> Invoice:
        invoice = self._editable(invoice_id)
        appointment = self._appointments.get(appointment_id)
        if appointment.patient_id != invoice.patient_id:
            raise BillingError("appointment belongs to a different patient")
        if appointment.status is not AppointmentStatus.COMPLETED:
            raise BillingError("only completed appointments can be billed")
        if self._invoices.appointment_already_billed(appointment_id):
            raise BillingError("appointment has already been billed")
        invoice.items.append(
            LineItem(
                description=f"{appointment.procedure_code.title()} on {appointment.start:%Y-%m-%d}",
                amount_cents=config.PROCEDURE_PRICES_CENTS[appointment.procedure_code],
                procedure_code=appointment.procedure_code,
                appointment_id=appointment.id,
            )
        )
        return self._invoices.update(invoice)

    def add_custom_item(self, invoice_id: str, description: str, amount_cents: int) -> Invoice:
        invoice = self._editable(invoice_id)
        if amount_cents <= 0:
            raise ValidationError("custom items must have a positive amount")
        invoice.items.append(LineItem(description=description, amount_cents=amount_cents))
        return self._invoices.update(invoice)

    def charge_no_show_fee(self, appointment_id: str) -> Invoice:
        appointment = self._appointments.get(appointment_id)
        if appointment.status is not AppointmentStatus.NO_SHOW:
            raise BillingError("no-show fee only applies to no-show appointments")
        invoice = self.create_invoice(appointment.patient_id)
        invoice.items.append(
            LineItem("No-show fee", config.NO_SHOW_FEE_CENTS, appointment_id=appointment.id)
        )
        invoice.status = InvoiceStatus.FINALIZED
        invoice.finalized_at = self._clock.now()
        invoice.patient_owes_cents = config.NO_SHOW_FEE_CENTS
        return self._invoices.update(invoice)

    def finalize_invoice(self, invoice_id: str) -> Invoice:
        invoice = self._editable(invoice_id)
        if not invoice.items:
            raise BillingError("cannot finalize an empty invoice")
        today = self._clock.now().date()
        policy = self._insurance.get_active_policy_for_patient(invoice.patient_id, today)
        if policy is None:
            invoice.patient_owes_cents = invoice.subtotal_cents
        else:
            claim = self._insurance.calculate_claim(policy, invoice.subtotal_cents)
            invoice.insurer_pays_cents = claim.insurer_pays_cents
            invoice.patient_owes_cents = claim.patient_owes_cents
            invoice.deductible_applied_cents = claim.deductible_applied_cents
        invoice.status = InvoiceStatus.FINALIZED
        invoice.finalized_at = self._clock.now()
        return self._invoices.update(invoice)

    def record_payment(self, invoice_id: str, amount_cents: int) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice.status is not InvoiceStatus.FINALIZED:
            raise BillingError("payments can only be recorded against finalized invoices")
        if amount_cents <= 0:
            raise ValidationError("payment must be positive")
        if amount_cents > invoice.balance_cents:
            raise BillingError("payment exceeds the outstanding balance")
        invoice.paid_cents += amount_cents
        if invoice.balance_cents == 0:
            invoice.status = InvoiceStatus.PAID
        return self._invoices.update(invoice)

    def void_invoice(self, invoice_id: str) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.VOID):
            raise BillingError(f"cannot void a {invoice.status.value} invoice")
        invoice.status = InvoiceStatus.VOID
        return self._invoices.update(invoice)

    def outstanding_for_patient(self, patient_id: str) -> int:
        return sum(
            inv.balance_cents
            for inv in self._invoices.for_patient(patient_id)
            if inv.status is InvoiceStatus.FINALIZED
        )

    def _editable(self, invoice_id: str) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if not invoice.is_editable:
            raise BillingError(f"invoice {invoice_id} is {invoice.status.value} and cannot be changed")
        return invoice
