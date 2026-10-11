from dataclasses import dataclass
from datetime import date


@dataclass
class InsurancePolicy:
    id: str
    patient_id: str
    plan_name: str
    member_id: str
    coverage_pct: int           # insurer's share of post-deductible, post-copay charges
    copay_cents: int            # flat amount per invoice
    deductible_cents: int       # annual deductible
    expires_on: date
    deductible_met_cents: int = 0

    @property
    def remaining_deductible_cents(self) -> int:
        return max(0, self.deductible_cents - self.deductible_met_cents)

    def is_active(self, on: date) -> bool:
        return on <= self.expires_on


@dataclass(frozen=True)
class ClaimResult:
    charge_cents: int
    deductible_applied_cents: int
    copay_cents: int
    coinsurance_cents: int
    insurer_pays_cents: int

    @property
    def patient_owes_cents(self) -> int:
        return self.deductible_applied_cents + self.copay_cents + self.coinsurance_cents
