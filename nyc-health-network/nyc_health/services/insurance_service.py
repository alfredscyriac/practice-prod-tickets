from datetime import date
from typing import Optional

from nyc_health.exceptions import BillingError
from nyc_health.models.insurance import ClaimResult, InsurancePolicy
from nyc_health.repositories.insurance_repo import PolicyRepository
from nyc_health.utils.money import percent_of


class InsuranceService:
    def __init__(self, policies: PolicyRepository) -> None:
        self._policies = policies

    def get_active_policy_for_patient(self, patient_id: str, on: date) -> Optional[InsurancePolicy]:
        policy = self._policies.for_patient(patient_id)
        if policy is None or not policy.is_active(on):
            return None
        return policy

    def calculate_claim(self, policy: InsurancePolicy, charge_cents: int) -> ClaimResult:
        """Pure calculation: what the insurer and the patient would each pay for `charge_cents`.

        Order of operations: deductible first, then the flat copay, then coinsurance on the rest.
        """
        if charge_cents < 0:
            raise BillingError("charge cannot be negative")
        deductible = min(charge_cents, policy.remaining_deductible_cents)
        remaining = charge_cents - deductible
        copay = min(policy.copay_cents, remaining)
        remaining -= copay
        insurer_pays = percent_of(remaining, policy.coverage_pct)
        return ClaimResult(
            charge_cents=charge_cents,
            deductible_applied_cents=deductible,
            copay_cents=copay,
            coinsurance_cents=remaining - insurer_pays,
            insurer_pays_cents=insurer_pays,
        )

    def apply_claim(self, policy_id: str, charge_cents: int) -> ClaimResult:
        """Calculate a claim and record the deductible consumed on the policy."""
        policy = self._policies.get(policy_id)
        result = self.calculate_claim(policy, charge_cents)
        policy.deductible_met_cents += result.deductible_applied_cents
        self._policies.update(policy)
        return result

    def release_deductible(self, policy_id: str, amount_cents: int) -> InsurancePolicy:
        """Give back deductible credit (e.g. when a claim is voided)."""
        policy = self._policies.get(policy_id)
        policy.deductible_met_cents = max(0, policy.deductible_met_cents - amount_cents)
        return self._policies.update(policy)
