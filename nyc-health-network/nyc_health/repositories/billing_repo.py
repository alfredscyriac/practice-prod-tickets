from typing import List

from nyc_health.models.billing import Invoice, InvoiceStatus
from nyc_health.repositories.base import InMemoryRepository


class InvoiceRepository(InMemoryRepository[Invoice]):
    entity_name = "invoice"
    id_prefix = "INV"

    def for_patient(self, patient_id: str) -> List[Invoice]:
        return sorted(self.find(lambda i: i.patient_id == patient_id), key=lambda i: i.created_at)

    def by_status(self, status: InvoiceStatus) -> List[Invoice]:
        return self.find(lambda i: i.status is status)

    def appointment_already_billed(self, appointment_id: str) -> bool:
        return any(
            appointment_id in inv.billed_appointment_ids()
            for inv in self.find(lambda i: i.status is not InvoiceStatus.VOID)
        )
