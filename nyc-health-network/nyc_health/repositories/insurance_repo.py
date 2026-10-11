from typing import Optional

from nyc_health.models.insurance import InsurancePolicy
from nyc_health.repositories.base import InMemoryRepository


class PolicyRepository(InMemoryRepository[InsurancePolicy]):
    entity_name = "insurance policy"
    id_prefix = "POL"

    def for_patient(self, patient_id: str) -> Optional[InsurancePolicy]:
        matches = self.find(lambda p: p.patient_id == patient_id)
        return matches[-1] if matches else None
