from typing import Optional

from nyc_health.models.insurance import InsurancePolicy
from nyc_health.repositories.base import MongoRepository


class PolicyRepository(MongoRepository[InsurancePolicy]):
    entity_name = "insurance policy"
    id_prefix = "POL"
    collection_name = "policies"
    model = InsurancePolicy
    indexes = [("patient_id",)]

    def for_patient(self, patient_id: str) -> Optional[InsurancePolicy]:
        matches = self.find_where({"patient_id": patient_id}, sort=[("_id", 1)])
        return matches[-1] if matches else None
