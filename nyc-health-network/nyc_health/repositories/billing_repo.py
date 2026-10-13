from typing import List

from nyc_health.models.billing import Invoice, InvoiceStatus
from nyc_health.repositories.base import MongoRepository


class InvoiceRepository(MongoRepository[Invoice]):
    entity_name = "invoice"
    id_prefix = "INV"
    collection_name = "invoices"
    model = Invoice
    indexes = [("patient_id",)]

    def for_patient(self, patient_id: str) -> List[Invoice]:
        return self.find_where({"patient_id": patient_id}, sort=[("created_at", 1)])

    def by_status(self, status: InvoiceStatus) -> List[Invoice]:
        return self.find_where({"status": status.value})

    def appointment_already_billed(self, appointment_id: str) -> bool:
        return any(
            appointment_id in inv.billed_appointment_ids()
            for inv in self.find_where({"status": {"$ne": InvoiceStatus.VOID.value}})
        )
