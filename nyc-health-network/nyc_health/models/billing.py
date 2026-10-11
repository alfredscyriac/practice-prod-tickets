from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class InvoiceStatus(Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PAID = "paid"
    VOID = "void"


@dataclass
class LineItem:
    description: str
    amount_cents: int
    procedure_code: Optional[str] = None
    appointment_id: Optional[str] = None


@dataclass
class Invoice:
    id: str
    patient_id: str
    created_at: datetime
    items: List[LineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.DRAFT
    finalized_at: Optional[datetime] = None
    insurer_pays_cents: int = 0
    patient_owes_cents: int = 0
    deductible_applied_cents: int = 0
    paid_cents: int = 0

    @property
    def subtotal_cents(self) -> int:
        return sum(item.amount_cents for item in self.items)

    @property
    def balance_cents(self) -> int:
        return self.patient_owes_cents - self.paid_cents

    @property
    def is_editable(self) -> bool:
        return self.status is InvoiceStatus.DRAFT

    def billed_appointment_ids(self) -> set:
        return {item.appointment_id for item in self.items if item.appointment_id}
